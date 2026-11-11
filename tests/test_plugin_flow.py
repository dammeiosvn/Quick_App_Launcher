from flow_model import Runner, USER, PLUGIN, to_text
FLAG=USER/'QuickAccessHint-v1.txt'
class DeviceModel(Runner):
    def __init__(self,*args,installed=True,appname='Facebook',**kwargs):
        super().__init__(*args,**kwargs)
        self.installed,self.appname=installed,appname
        self.home=[]
    def action(self,kind,p):
        if kind=='getmyworkflows':return [{'Name':PLUGIN}] if self.installed else []
        if kind=='text.replace' and p['WFInput'].get('WFSerializationType')!='WFTextTokenString':
            return '' # reproduces the empty source seen in the iPhone recording
        if kind=='searchappstore':return [{'Name':self.appname,'Store URL':'https://apps.apple.com/app/id1','Bundle Identifier':'com.example.app','Artwork':b'png','Download Size':'50 MB'}]
        if kind=='choosefromlist':
            choices=self.resolve(p.get('WFInput'))
            if isinstance(choices,list) and choices and isinstance(choices[0],dict) and 'Artwork' in choices[0]:return choices[0]
        if kind=='image.resize':return b'png'
        if kind=='base64encode':return 'cG5n'
        if kind=='openurl':self.urls.append(self.resolve(p['WFInput']));return
        if kind=='com.apple.shortcuts.AddShortcutToHomeScreenAction':
            assert p['shortcut']['title']['key']==PLUGIN
            self.home.append(PLUGIN);return
        return super().action(kind,p)

fresh=DeviceModel(5,menus=[0]).run()
warm=DeviceModel(5,fresh.files,routes=['open_apps'],menus=[2]).run()
assert warm.plugins==[PLUGIN] and FLAG not in warm.files
missing=DeviceModel(5,warm.files,routes=['open_apps'],installed=False).run()
assert not missing.plugins and not missing.home and FLAG not in missing.files
assert missing.urls==['https://www.icloud.com/shortcuts/abe06a3f96834c369d5a5bcd6b22a32e']
assert 'Thêm phím tắt' in missing.notices[-1]
home=DeviceModel(5,warm.files,routes=['open_apps'],menus=[0]).run()
assert home.plugins==[PLUGIN] and home.home==[PLUGIN] and home.files[FLAG]==b'home_screen'
again=DeviceModel(5,home.files,routes=['open_apps']).run()
assert again.plugins==[PLUGIN] and not again.home and not again.menus and not again.writes
removed=DeviceModel(5,home.files,routes=['open_apps'],installed=False).run()
assert not removed.plugins and len(removed.urls)==1
cc=DeviceModel(5,warm.files,routes=['open_apps'],menus=[1]).run()
assert 'Trung tâm điều khiển' in cc.notices[-1] and FLAG not in cc.files
no_pack=DeviceModel(5,menus=[1,0]).run()
assert no_pack.files[FLAG]==b'home_screen' and no_pack.urls==['shortcuts://open-shortcut?name=Plugin_Quickapplauncher']
old=DeviceModel(4,warm.files,routes=['add_app'],menus=[0,0]).run()
assert 'Thiếu tên ứng dụng' in old.notices[-1]
for name in ['Facebook','Threads','TikTok-Global Video Community','A/B: C;D, E']:
    app=DeviceModel(5,warm.files,routes=['add_app'],menus=[0,0],appname=name).run()
    files=[p for p in app.writes if p.parent==USER/'AppList']
    assert len(files)==1 and app.files[files[0]].startswith(b'BEGIN:VCARD')
    assert FLAG not in app.files and app.plugins==[PLUGIN]
    duplicate=DeviceModel(5,app.files,routes=['add_app'],menus=[0,0],appname=name).run()
    assert not duplicate.writes and 'Đã có mục cùng tên' in duplicate.notices[-1]
print('PASS: missing/reinstalled plugin, after-return hint, Home Screen flag, repeat run, Later, Control Center, no-data fallback')
print('PASS: recorded beta4 empty Replace input; beta5 App Store save for four names; duplicate guard and no unexpected onboarding')
