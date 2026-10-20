import copy, json, threading, time
from pathlib import Path
import pytest
from app.models.profile import Application, Profile
from app.services.config_service import ConfigService
from app.core.scheduler import Scheduler
from app.core.launcher import Target, split_arguments, resolve, launch

def item(name='测试', **kw):return Application(name,'C:/测试 路径/app.exe',launch_strategy='immediate',**kw)
def engine(**kw):
    calls=[]; events=[]
    deps=dict(resolver=lambda a:Target(a.path),launcher=lambda t:calls.append(t.path),monitor=lambda **k:([],False),checker=lambda a,t:True)
    deps.update(kw)
    return Scheduler(lambda *x:events.append(x),**deps),calls,events

def test_config_crud_copy_order(tmp_path):
    c=ConfigService(tmp_path);p=Profile('开发',applications=[item('A'),item('B')]);c.profiles.append(p);c.save()
    p.name='办公';p.description='描述';p.applications.reverse();q=p.clone();c.profiles.append(q);c.save()
    assert q.id!=p.id and q.applications[0].id!=p.applications[0].id
    restored=ConfigService(tmp_path);assert restored.profiles[0].name=='办公'
    assert [a.name for a in restored.profiles[0].applications]==['B','A']
    restored.profiles[0].applications.pop();restored.profiles.pop();restored.save();assert len(ConfigService(tmp_path).profiles)==1

def test_backup_recovery(tmp_path):
    c=ConfigService(tmp_path);c.profiles=[Profile('原始')];c.save();c.profiles[0].name='新名称';c.save()
    (tmp_path/'profiles.json').write_text('{broken');c=ConfigService(tmp_path);assert c.profiles[0].name=='原始';assert c.warnings
    c.save();assert ConfigService(tmp_path).profiles[0].name=='原始'

def test_legacy_arguments_and_version():
    p=ConfigService.parse(dict(profiles=[dict(name='旧版',applications=[dict(name='应用',path='app.exe',arguments=['带 空格','中文'],readiness=None)])]))[0]
    assert split_arguments(p.applications[0].arguments)==['带 空格','中文']
    with pytest.raises(ValueError):ConfigService.parse(dict(schema_version=99,profiles=[]))

@pytest.mark.parametrize('field,value',[('delay_seconds',3601),('retry_count',4),('launch_strategy','bad'),('failure_action','bad')])
def test_validation(field,value):
    a=item();setattr(a,field,value)
    with pytest.raises(ValueError):a.validate()

def test_sequential_disabled_snapshot_and_conflict():
    a=item('A');b=item('B');b.path='B.exe';p=Profile('开发',applications=[a,item('禁用',enabled=False),b]);s,c,e=engine()
    snapshot=s.reserve(p);assert s.reserve(Profile('办公')) is None
    p.applications.reverse();result=s.run(snapshot);assert c==[a.path,b.path] and result['started']==2 and s.active is None

def test_running_still_waits_independent_tcp():
    a=item();a.launch_strategy='ready';a.readiness.update(kind='tcp',interval=.1,timeout=1)
    checks=[]
    def check(a,t):checks.append(1);return len(checks)>=2
    s,c,e=engine(monitor=lambda **k:([99],False),checker=check);result=s.run(s.reserve(Profile('P',applications=[a])))
    assert c==[] and len(checks)==2 and result['skipped']==1

def test_uncertain_does_not_duplicate():
    s,c,e=engine(monitor=lambda **k:([],True));r=s.run(s.reserve(Profile('P',applications=[item()])));assert not c and r['failed']==1

@pytest.mark.parametrize('action,expected',[('continue',2),('stop',1),('retry',3)])
def test_failure_policies(action,expected):
    attempts=[]
    def launch(t):attempts.append(t);raise OSError('拒绝执行')
    a=item(failure_action=action,retry_count=1,retry_interval=0)
    s,c,e=engine(launcher=launch);s.run(s.reserve(Profile('P',applications=[a,item('B')])));assert len(attempts)==expected

def test_retry_ready_does_not_relaunch_accepted_command():
    a=item(failure_action='retry',retry_count=1,retry_interval=0);a.launch_strategy='ready';a.readiness.update(timeout=.1,interval=.1)
    s,c,e=engine(checker=lambda a,t:False);r=s.run(s.reserve(Profile('P',applications=[a])))
    assert len(c)==1 and r['failed']==1 and r['started']==1

def test_cancel_wait_no_next_launch():
    a=item();a.launch_strategy='delay';a.delay_seconds=5;s,c,e=engine();p=s.reserve(Profile('P',applications=[a,item('B')]))
    thread=threading.Thread(target=s.run,args=(p,));thread.start();time.sleep(.05);s.cancel();thread.join(1)
    assert not thread.is_alive() and len(c)==1 and any(x[0]=='finished' for x in e)

def test_delay():
    a=item();a.launch_strategy='delay';a.delay_seconds=.12;s,c,e=engine();start=time.monotonic();s.run(s.reserve(Profile('P',applications=[a])));assert time.monotonic()-start>=.12

def test_paths_and_exe_args(tmp_path,monkeypatch):
    path=tmp_path/'中文 空格.exe';path.touch();a=Application('测试',str(path),arguments='"中文 空格" --flag');target=resolve(a);captured=[]
    monkeypatch.setattr('subprocess.Popen',lambda *a,**k:captured.append((a,k)))
    launch(target);assert captured[0][0][0]==[str(path),'中文 空格','--flag'];assert captured[0][1]['shell'] is False
    with pytest.raises(FileNotFoundError):resolve(Application('丢失',str(tmp_path/'missing.exe')))

def test_tcp_readiness():
    import socket
    from app.core.readiness_checker import check
    a=item();a.readiness['kind']='tcp'
    with socket.socket() as server:
        server.bind(('127.0.0.1',0));server.listen();a.readiness['port']=server.getsockname()[1];assert check(a,Target(a.path))
    assert not check(a,Target(a.path))

@pytest.mark.parametrize('outcome',['completed','failed','stopped'])
def test_finish_state_is_explicit(outcome):
    def launcher(target):
        if outcome=='failed':raise OSError('测试失败')
    s,c,events=engine(launcher=launcher)
    profile=s.reserve(Profile('结果',applications=[item()]))
    if outcome=='stopped':s.cancel()
    s.run(profile)
    finished=[e for e in events if e[0]=='finished'][-1]
    assert finished[1]==outcome
    assert {'completed':'启动流程完成','failed':'有失败项','stopped':'启动流程已停止'}[outcome] in finished[2]
