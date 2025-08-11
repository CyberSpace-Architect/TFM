from cx_Freeze import setup, Executable

icon_path = "media/icon.ico"
families_path = r"D:\Program Files\PyCharm 2024.3.2\workspace\Conflict Watcher\.venv\Lib\site-packages\pywikibot\families"
main_script = "app/main.py"

build_exe_options = {
    "packages": ["pywikibot"],
    "include_files": [
        (families_path, "config/families"),
        ("build_config", "config"),
    ],
}

setup(
    name="Conflict Watcher",
    version="1.0",
    description="Tool for detection and monitoring of edit wars in Wikipedia",
    options={"build_exe": build_exe_options},
    executables=[Executable(main_script, base=None, icon=icon_path, target_name="Conflict Watcher.exe")],
)
