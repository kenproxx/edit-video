"""Source and packaged entry point; dependencies are installed by setup/build."""

def main() -> None:
    from app.ui import VideoEditorApp
    app = VideoEditorApp()
    app.mainloop()


if __name__ == '__main__':
    main()
