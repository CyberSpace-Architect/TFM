from cx_Freeze import setup, Executable

icon_path = "media/icon.ico"
families_path = r"D:\Program Files\PyCharm 2024.3.2\workspace\Conflict Watcher\.venv\Lib\site-packages\pywikibot\families"
main_script = "app/main.py"
#pywikibot_path = r"D:\Program Files\PyCharm 2024.3.2\workspace\Conflict Watcher\.venv\Lib\site-packages\pywikibot"

build_exe_options = {
    "packages": ["pywikibot"],
    "include_files": [
        #(pywikibot_path, "pywikibot")
        (families_path, "config/families"),
        #(families_path, "."),
        ("build_config", "config"),
        #("build_config", "."),
    ],
}

setup(
    name="Conflict Watcher",
    version="1.0",
    description="Tool for detection and monitoring of edit wars in Wikipedia",
    options={"build_exe": build_exe_options},
    executables=[Executable(main_script, base=None, icon=icon_path, target_name="Conflict Watcher.exe")],
)
