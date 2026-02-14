1. Generate main_window.spec `pyi-makespec --onefile --windowed main_window.py`
2. edit a line: `datas=[('lang', 'lang')],`
3. run build: `pyinstaller main_window.spec`