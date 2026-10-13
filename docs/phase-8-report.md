name: Build EXE and attach version release
on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      tag:
        description: 'New version, e.g. v0.2.0 (builds main)'
        required: true
permissions:
  contents: read
concurrency:
  group: version-release-${{ github.event.inputs.tag || github.ref_name }}
  cancel-in-progress: false
jobs:
  validate:
    if: github.event_name == 'push' || github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    env:
      RELEASE_TAG: ${{ github.event.inputs.tag || github.ref_name }}
    steps:
      - name: Validate version before building
        shell: bash
        run: |
          [[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]
  build:
    needs: validate
    name: build
    if: github.event_name == 'push' || github.ref == 'refs/heads/main'
    uses: ./.github/workflows/windows-build.yml
  release:
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write
      actions: read
    env:
      GH_TOKEN: ${{ github.token }}
      RELEASE_TAG: ${{ github.event.inputs.tag || github.ref_name }}
    steps:
      - uses: actions/checkout@v4
      - name: Verify version, tag and existing release before attachment
        shell: bash
        run: |
          set -euo pipefail
          [[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]
          python3 - <<'PY'
          import json,os,subprocess
          repo=os.environ['GITHUB_REPOSITORY'];tag=os.environ['RELEASE_TAG'];sha=os.environ['GITHUB_SHA']
          releases=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases','--paginate','--slurp']))
          existing=next((r for page in releases for r in page if r['tag_name']==tag),None)
          ref=subprocess.run(['git','ls-remote','origin',f'refs/tags/{tag}',f'refs/tags/{tag}^{{}}'],check=True,capture_output=True,text=True).stdout.splitlines()
          if ref:
              resolved=next((line.split()[0] for line in ref if line.endswith('^{}')),ref[0].split()[0])
              if resolved!=sha: raise SystemExit('Version tag points at a different commit')
          if existing:
              if not existing['draft'] or existing['target_commitish']!=sha: raise SystemExit('Existing release must be a matching draft')
          else:
              subprocess.run(['gh','release','create',tag,'--repo',repo,'--target',sha,'--draft','--title',f'VideoEditor {tag}','--notes','Verified Windows x64 EXE. Release remains draft pending the matching FFmpeg corresponding-source bundle.'],check=True)
          PY
      - name: Retrieve this run and verified Windows artifact
        shell: bash
        run: |
          set -euo pipefail
          gh api "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" > run.json
          gh api "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/jobs?filter=all&per_page=100" --paginate --jq '.jobs[]' | jq -s '{jobs:.}' > jobs.json
          gh api "repos/$GITHUB_REPOSITORY/releases" --paginate --jq ".[] | select(.tag_name == \"$RELEASE_TAG\")" > release.json
          gh api "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts" --jq '.artifacts | map(select(.name == "VideoEditor-windows-x64" and .expired == false)) | if length == 1 then .[0] else error("Expected one verified artifact") end' > artifact.json
          artifact_id=$(python3 -c 'import json; print(json.load(open("artifact.json"))["id"])')
          gh api "repos/$GITHUB_REPOSITORY/actions/artifacts/$artifact_id/zip" > artifact.zip
          python3 scripts/prepare-release.py --archive artifact.zip --artifact-json artifact.json --release-json release.json --run-json run.json --build-jobs-json jobs.json --output-dir release-assets
      - name: Attach verified assets without replacing existing files
        shell: bash
        run: |
          python3 - <<'PY'
          import hashlib,json,os,subprocess
          repo=os.environ['GITHUB_REPOSITORY'];tag=os.environ['RELEASE_TAG']
          release=json.load(open('release.json'))
          current=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases/{release["id"]}']))
          if not current['draft'] or current['target_commitish']!=os.environ['GITHUB_SHA']: raise SystemExit('Draft release changed')
          existing={a['name']:a for a in current['assets']}
          for path in json.load(open('release-assets/upload-files.json')):
              name=os.path.basename(path)
              with open(path,'rb') as stream: expected='sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
              if name in existing:
                  if existing[name].get('digest')!=expected: raise SystemExit('Existing release asset differs: '+name)
                  continue
              subprocess.run(['gh','release','upload',tag,path,'--repo',repo],check=True)
          PY
