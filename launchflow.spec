# Run: python -m PyInstaller --noconfirm launchflow.spec
import os
onefile = os.environ.get('LAUNCHFLOW_ONEFILE') == '1'
a = Analysis(['main.py'], pathex=[], binaries=[], datas=[('LICENSE','.'), ('THIRD_PARTY_NOTICES.md','.')], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
if onefile:
    exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='LaunchFlow',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
else:
    exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='LaunchFlow',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
    coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='LaunchFlow')
