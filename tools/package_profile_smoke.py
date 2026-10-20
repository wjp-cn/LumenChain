import json, os, socket, subprocess, tempfile, time, sys
from pathlib import Path
exe=Path(sys.argv[1] if len(sys.argv)>1 else 'dist/LaunchFlow/LaunchFlow.exe').resolve()
with tempfile.TemporaryDirectory() as directory, socket.socket() as server:
    root=Path(directory);server.bind(('127.0.0.1',0));port=server.getsockname()[1]
    first_output=root/'first.txt';second_output=root/'second.txt'
    profiles=[]
    for name,output in [('first',first_output),('second',second_output)]:
        script=root/(name+' test.cmd');script.write_text('@echo off\r\n> "'+str(output)+'" echo accepted\r\n',encoding='utf-8')
        app=dict(name=name,path=str(script),launch_strategy='ready' if name=='first' else 'immediate',skip_if_running=False)
        if name=='first':app['readiness']=dict(kind='tcp',value='',host='127.0.0.1',port=port,timeout=18,interval=.1,associate=False)
        profiles.append(dict(id=name,name=name,applications=[app]))
    data=root/'LaunchFlow';data.mkdir();(data/'profiles.json').write_text(json.dumps(dict(schema_version=1,profiles=profiles)),encoding='utf-8')
    env=os.environ.copy();env['APPDATA']=str(root);env['QT_QPA_PLATFORM']='windows'
    first=subprocess.Popen([str(exe),'--minimized','--profile','first','--smoke-test','--smoke-timeout','20000'],env=env,cwd=root)
    try:
        deadline=time.monotonic()+15
        while not first_output.exists() and time.monotonic()<deadline and first.poll() is None:time.sleep(.03)
        assert first_output.exists(),'profile parameter did not launch temporary script'
        second=subprocess.run([str(exe),'--profile','second'],env=env,cwd=root,timeout=25)
        assert second.returncode==0
        assert not second_output.exists(),'conflicting profile launched'
        server.listen();assert first.wait(timeout=30)==0
        text=(data/'logs/launchflow.log').read_text(encoding='utf-8');assert 'ERROR' not in text,text
        assert not second_output.exists()
        result=dict(exe=str(exe),profile_parameter=True,real_script=True,cross_profile_conflict_blocked=True,independent_tcp_readiness=True,clean_exit=True)
        suffix='onedir' if exe.parent.name=='LaunchFlow' else 'onefile'
        Path('docs/package-profile-'+suffix+'.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    finally:
        if first.poll() is None:first.terminate();first.wait(timeout=5)
