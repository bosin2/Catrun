"""Author the editable MainMenu additions and settings Designer/event graphs.

Run only in the root-owned UnrealEditor-Cmd lease after the C++ build.
Never creates a game world or applies host settings while authoring.
"""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, Graph, add, audit, compile_bp, editor, entry, event, function, literal, pin, properties, ui, widgets, wire, PROPERTY_SCHEMAS

OUT = ROOT / 'Saved/Menu20261105'
OUT.mkdir(exist_ok=True)
MANIFEST = OUT / 'author-manifest.json'
manifest = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'assets': []}
MAIN_PATH = '/Game/UI/WBP_MainMenu'
SETTINGS_PATH = '/Game/UI/Settings/WBP_Setting'
AS = unreal.EditorAssetLibrary

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def progress(label):
    (OUT/'author-progress.txt').write_text(label,encoding='utf-8')
    print('MENU_PROGRESS '+label)

def backup(path):
    if any(a['asset'] == path for a in manifest['assets']):
        return
    package = path.removeprefix('/Game/')
    file = ROOT / 'Content' / (package + '.uasset')
    dest = OUT / 'AuthorBackups' / (package + '.uasset')
    dirty = {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    dirty.update(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert path not in dirty, 'Target is dirty before authoring: ' + path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, dest)
    manifest['assets'].append({'asset': path, 'backup': str(dest),
        'before_sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    write_json(MANIFEST, manifest)

def color(hex_value, alpha=1.0):
    h = hex_value.lstrip('#')
    def linear(channel):
        value=int(channel,16)/255.0
        return value/12.92 if value<=0.04045 else ((value+0.055)/1.055)**2.4
    return unreal.LinearColor(linear(h[:2]),linear(h[2:4]),linear(h[4:6]),alpha)

GRAPHITE, SLATE, GOLD, IVORY, MUTED = [color(h) for h in ('252831','343641','D8B66B','F3E5C8','A4A4AB')]
FONT = AS.load_asset('/Game/Environment/Font/HSBombaram3_0_Regular_Font')
assert FONT

def font(size):
    return unreal.SlateFontInfo(font_object=FONT, typeface_font_name='Default', size=size)

def brush(c):
    return unreal.SlateBrush(tint_color=unreal.SlateColor(specified_color=c), draw_as=unreal.SlateBrushDrawType.BOX,
                             margin=unreal.Margin(0.0))

def text(bp, name, label, parent, size=22, tint=IVORY, variable=False):
    w = add(bp, unreal.TextBlock, name, parent, variable)
    properties(w, text=unreal.Text(label), font=font(size), color_and_opacity=unreal.SlateColor(specified_color=tint))
    return w

def pad(w, left=0, top=0, right=0, bottom=0):
    slot = w.get_editor_property('slot')
    properties(slot, padding=unreal.Margin(left, top, right, bottom))

def canvas(w, amin, amax, offsets, z=0, alignment=(0,0), autosize=False):
    slot = w.get_editor_property('slot')
    properties(slot, layout_data=unreal.AnchorData(offsets=unreal.Margin(*offsets),
        anchors=unreal.Anchors(minimum=unreal.Vector2D(*amin), maximum=unreal.Vector2D(*amax)),
        alignment=unreal.Vector2D(*alignment)), z_order=z, auto_size=autosize)

def sizebox(bp, name, parent, width=None, height=None):
    w = add(bp, unreal.SizeBox, name, parent)
    if width is not None:
        w.set_width_override(width)
    if height is not None:
        w.set_height_override(height)
    return w

def button(bp, name, label, parent, primary=False):
    w = add(bp, unreal.Button, name, parent, True)
    style = w.get_editor_property('widget_style')
    for k,c in (('normal', GOLD if primary else SLATE),
                ('hovered',color('E7CA86' if primary else '4C4B48')),
                ('pressed',color('B39556' if primary else '615640'))):
        style.set_editor_property(k, brush(c))
    style.set_editor_property('normal_padding', unreal.Margin(18,9,18,9))
    style.set_editor_property('pressed_padding', unreal.Margin(18,10,18,8))
    properties(w, widget_style=style, is_focusable=True)
    text(bp, name+'Text', label, w, 22, GRAPHITE if primary else IVORY)
    return w

def combo(bp, name, parent, options):
    w = add(bp, unreal.ComboBoxString, name, parent, True)
    properties(w, default_options=options, selected_option=options[0], font=font(22),
        foreground_color=unreal.SlateColor(specified_color=IVORY), content_padding=unreal.Margin(14,7,14,7),
        max_list_height=280.0, is_focusable=True, enable_gamepad_navigation_mode=True)
    style=w.get_editor_property('widget_style')
    bs=style.get_editor_property('combo_button_style')
    b=bs.get_editor_property('button_style')
    b.set_editor_property('normal',brush(SLATE))
    b.set_editor_property('hovered',brush(color('4C4B48')))
    b.set_editor_property('pressed',brush(color('615640')))
    bs.set_editor_property('button_style',b)
    bs.set_editor_property('menu_border_brush',brush(GRAPHITE))
    style.set_editor_property('combo_button_style',bs)
    properties(w,widget_style=style)
    rows=w.get_editor_property('item_style')
    for k,c in [('even_row_background_brush',GRAPHITE),('odd_row_background_brush',GRAPHITE),
                ('even_row_background_hovered_brush',SLATE),('odd_row_background_hovered_brush',SLATE),
                ('active_brush',SLATE),('inactive_brush',SLATE),('selector_focused_brush',color('62573E'))]:
        rows.set_editor_property(k,brush(c))
    rows.set_editor_property('text_color',unreal.SlateColor(specified_color=IVORY))
    rows.set_editor_property('selected_text_color',unreal.SlateColor(specified_color=GOLD))
    properties(w,item_style=rows)
    return w

def checkbox(bp, name, parent):
    w=add(bp,unreal.CheckBox,name,parent,True)
    properties(w,is_focusable=True)
    return w

def row(bp, name, label, parent):
    box=sizebox(bp,name+'Height',parent,height=58)
    h=add(bp,unreal.HorizontalBox,name,box)
    t=text(bp,name+'Label',label,h)
    properties(t.get_editor_property('slot'), size=unreal.SlateChildSize(value=1.0,size_rule=unreal.SlateSizeRule.FILL),
               vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
    right=sizebox(bp,name+'ControlWidth',h,width=340)
    properties(right.get_editor_property('slot'),vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
    return right

# All function names and pin names below are native reflected APIs, not display titles.
S='/Script/Catrun.CatrunUserSettings.'
U='/Script/Engine.GameUserSettings.'
W='/Script/UMG.Widget.'
T='/Script/UMG.TextBlock.'
C='/Script/UMG.ComboBoxString.'
K='/Script/Engine.KismetMathLibrary.'

def settings(q):
    return (q.fn(S+'GetCatrunUserSettings'),'ReturnValue')

def widget_call(q,name,path,**kw):
    return q.fn(path,target=q.ref(name),**kw)

def eq(q, source, value, kind='IntInt'):
    return q.fn(K+'EqualEqual_'+kind,A=source,B=value)

def call_local(q, name):
    return q.fn(name)

def index(q,widget):
    return (widget_call(q,widget,C+'GetSelectedIndex'),'ReturnValue')

def set_index(q,widget,value):
    return widget_call(q,widget,C+'SetSelectedIndex',Index=value)

def matching_init(bp, name, widget, source_path, matches, kind='IntInt'):
    q=function(bp,name)
    src=q.fn(source_path,target=settings(q))
    previous=entry(q); previous_pin='then'
    for current,selection in matches:
        compare=eq(q,(src,'ReturnValue'),current,kind)
        b=q.branch((compare,'ReturnValue'))
        wire(previous,previous_pin,b,'execute')
        setter=set_index(q,widget,selection)
        wire(b,'then',setter,'execute')
        previous,previous_pin=b,'else'
        q.y+=230; q.x=300
    q.comment('현재 값과 일치하는 항목만 선택. 지원 범위 밖 값은 현재 설정 유지.')

def matching_apply(bp,name,widget,target_path,matches,pin_name):
    q=function(bp,name)
    selected=index(q,widget)
    previous=entry(q); previous_pin='then'
    for choice,value in matches:
        compare=eq(q,selected,choice)
        b=q.branch((compare,'ReturnValue'))
        wire(previous,previous_pin,b,'execute')
        setter=q.fn(target_path,target=settings(q),**{pin_name:value})
        wire(b,'then',setter,'execute')
        previous,previous_pin=b,'else'
        q.y+=230; q.x=300
    q.comment('명시한 메뉴 선택만 적용. 현재 설정 유지는 원래 값을 보존.')

def main():
    backup(MAIN_PATH); backup(SETTINGS_PATH)
    main_bp=AS.load_asset(MAIN_PATH); bp=AS.load_asset(SETTINGS_PATH)
    original={n.get_name() for n in BP.find_nodes(BP.get_graph(main_bp,'EventGraph'))}
    mw=widgets(main_bp); sw=widgets(bp)
    assert 'VolumeSlider' not in sw, 'Already authored. Restore the owned binary backups before rerunning a changed author script.'
    assert set(sw)=={'CanvasPanel_29','Panel_Setting','List_Setting'}, list(sw)
    root,panel,body=sw['CanvasPanel_29'],sw['Panel_Setting'],sw['List_Setting']

    # Full-screen blocking scrim + an 840x760 panel that scales down to fit smaller viewports.
    scrim=add(bp,unreal.Border,'ModalScrim',root,index=0)
    properties(scrim,brush_color=unreal.LinearColor(0.018,0.021,0.028,0.88))
    canvas(scrim,(0,0),(1,1),(0,0,0,0))
    fit=add(bp,unreal.ScaleBox,'SettingsViewportFit',root)
    properties(fit,stretch=unreal.Stretch.SCALE_TO_FIT,stretch_direction=unreal.StretchDirection.DOWN_ONLY)
    canvas(fit,(0.04,0.04),(0.96,0.96),(0,0,0,0),1)
    bounds=sizebox(bp,'SettingsPanelBounds',fit,width=840,height=820)
    properties(bounds.get_editor_property('slot'),horizontal_alignment=unreal.HorizontalAlignment.H_ALIGN_CENTER,
               vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
    ui('MoveWidget',bp,panel,bounds,-1)
    panel_background=panel.get_editor_property('background')
    panel_background.set_editor_property('tint_color',unreal.SlateColor(specified_color=unreal.LinearColor(1,1,1,1)))
    properties(panel,background=panel_background,brush_color=GRAPHITE,padding=unreal.Margin(28,28,28,28),
               horizontal_alignment=unreal.HorizontalAlignment.H_ALIGN_FILL,
               vertical_alignment=unreal.VerticalAlignment.V_ALIGN_FILL)
    heading=add(bp,unreal.HorizontalBox,'SettingsHeading',body)
    title=text(bp,'SettingsTitle','설정',heading,36)
    properties(title.get_editor_property('slot'),size=unreal.SlateChildSize(value=1,size_rule=unreal.SlateSizeRule.FILL))
    ornament=sizebox(bp,'SettingsPawBounds',heading,width=36,height=36)
    paw=add(bp,unreal.Image,'SettingsPaw',ornament)
    paw.set_brush_from_texture(AS.load_asset('/Game/Environment/UI/CatJelly'),True)
    properties(paw,color_and_opacity=GOLD)
    hint=text(bp,'SettingsHint','소리와 화면을 편안하게 조절하세요.',body,18,MUTED)
    pad(hint,0,5,0,10)
    separator=sizebox(bp,'SettingsRuleHeight',body,height=2)
    line=add(bp,unreal.Border,'SettingsRule',separator)
    properties(line,brush_color=color('D8B66B',0.5))
    outer=body
    scroll=add(bp,unreal.ScrollBox,'SettingsBodyScroll',outer)
    properties(scroll.get_editor_property('slot'),size=unreal.SlateChildSize(value=1,size_rule=unreal.SlateSizeRule.FILL))
    body=add(bp,unreal.VerticalBox,'SettingsBody',scroll)
    group=text(bp,'GeneralGroupTitle','소리와 화면',body,23,GOLD); pad(group,0,15,0,5)
    volume=row(bp,'VolumeRow','전체 음량',body)
    vh=add(bp,unreal.HorizontalBox,'VolumeControl',volume)
    slider=add(bp,unreal.Slider,'VolumeSlider',vh,True)
    properties(slider,min_value=0.0,max_value=1.0,step_size=0.01,value=1.0,
               slider_bar_color=color('A4A4AB'),slider_handle_color=GOLD,is_focusable=True)
    properties(slider.get_editor_property('slot'),size=unreal.SlateChildSize(value=1,size_rule=unreal.SlateSizeRule.FILL),
               vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER,padding=unreal.Margin(0,0,14,0))
    pctbox=sizebox(bp,'VolumePercentWidth',vh,width=70)
    text(bp,'VolumePercent','100%',pctbox,22,IVORY,True)
    combo(bp,'WindowModeCombo',row(bp,'WindowModeRow','화면 모드',body),['현재 설정 유지','창 모드','테두리 없는 창'])
    combo(bp,'QualityCombo',row(bp,'QualityRow','그래픽 품질',body),['현재 설정 유지','낮음','보통','높음','최고'])
    combo(bp,'FrameLimitCombo',row(bp,'FrameLimitRow','프레임 제한',body),['현재 설정 유지','30','60','120','제한 없음'])
    checkbox(bp,'VSyncCheckBox',row(bp,'VSyncRow','수직 동기화',body))
    dev=add(bp,unreal.VerticalBox,'DeveloperGroup',body,True)
    properties(dev,visibility=unreal.SlateVisibility.COLLAPSED)
    devrule=sizebox(bp,'DeveloperRuleHeight',dev,height=1)
    devline=add(bp,unreal.Border,'DeveloperRule',devrule)
    properties(devline,brush_color=color('A4A4AB',0.3))
    dt=text(bp,'DeveloperGroupTitle','개발 테스트',dev,23,GOLD); pad(dt,0,12,0,3)
    text(bp,'DeveloperSessionHint','즉시 적용 · 이번 실행에만 유지',dev,18,MUTED)
    checkbox(bp,'NoArmorCaptureCheckBox',row(bp,'NoArmorCaptureRow','갑옷에게 잡히지 않기',dev))
    body=outer
    status=text(bp,'SettingsStatus','변경한 설정은 적용을 누르면 저장됩니다.',body,18,MUTED,True); pad(status,0,8,0,8)
    footer=add(bp,unreal.HorizontalBox,'SettingsFooter',body)
    footnote=text(bp,'CloseHint','닫기로 돌아가기',footer,18,MUTED)
    properties(footnote.get_editor_property('slot'),size=unreal.SlateChildSize(value=1,size_rule=unreal.SlateSizeRule.FILL),
               vertical_alignment=unreal.VerticalAlignment.V_ALIGN_CENTER)
    button(bp,'ApplyButton','적용',footer,True)
    close=button(bp,'CloseButton','닫기',footer)
    pad(close,12,0,0,0)
    BP.add_object_variable(bp,'ParentMenuWidget',unreal.UserWidget.static_class())
    BP.add_object_variable(bp,'ReturnFocusWidget',unreal.Widget.static_class())
    BP.add_variable(bp,'DraftReady','bool')
    compile_bp(bp)
    properties(unreal.get_default_object(bp.generated_class()),is_focusable=True)
    sw=widgets(bp)

    # Small named functions keep the EventGraph editable and understandable.
    function_names=['UpdateVolumePercent','InitializeWindowMode','InitializeQuality','InitializeFrameLimit',
                    'InitializeDraft','ApplyWindowMode','ApplyQuality','ApplyFrameLimit','ApplyDraft','CloseSettings','MarkDraftChanged']
    for name in function_names: function(bp,name)
    compile_bp(bp)
    q=function(bp,'UpdateVolumePercent')
    volumevalue=widget_call(q,'VolumeSlider','/Script/UMG.Slider.GetValue')
    percent=q.fn('/Script/Engine.KismetTextLibrary.AsPercent_Float',Value=(volumevalue,'ReturnValue'),MaximumFractionalDigits=0)
    st=widget_call(q,'VolumePercent',T+'SetText',InText=(percent,'ReturnValue')); q.chain(entry(q),st)
    q=function(bp,'MarkDraftChanged')
    st=widget_call(q,'SettingsStatus',T+'SetText',InText='변경한 설정은 적용을 누르면 저장됩니다.')
    q.chain(entry(q),st)

    matching_init(bp,'InitializeWindowMode','WindowModeCombo',U+'GetFullscreenMode',[(2,1),(1,2)],'ByteByte')
    matching_init(bp,'InitializeQuality','QualityCombo',U+'GetOverallScalabilityLevel',[(0,1),(1,2),(2,3),(3,4)])
    matching_init(bp,'InitializeFrameLimit','FrameLimitCombo',U+'GetFrameRateLimit',[(30,1),(60,2),(120,3),(0,4)],'DoubleDouble')
    matching_apply(bp,'ApplyWindowMode','WindowModeCombo',U+'SetFullscreenMode',[(1,'Windowed'),(2,'WindowedFullscreen')],'InFullscreenMode')
    matching_apply(bp,'ApplyQuality','QualityCombo',U+'SetOverallScalabilityLevel',[(1,0),(2,1),(3,2),(4,3)],'Value')
    matching_apply(bp,'ApplyFrameLimit','FrameLimitCombo',U+'SetFrameRateLimit',[(1,30),(2,60),(3,120),(4,0)],'NewLimit')

    q=function(bp,'InitializeDraft')
    ready=q.set('DraftReady',value=False)
    vol=q.fn(S+'GetMasterVolume',target=settings(q))
    setvol=widget_call(q,'VolumeSlider','/Script/UMG.Slider.SetValue',InValue=(vol,'ReturnValue'))
    pct=call_local(q,'UpdateVolumePercent')
    initmode=call_local(q,'InitializeWindowMode'); initquality=call_local(q,'InitializeQuality'); initfps=call_local(q,'InitializeFrameLimit')
    vs=q.fn(U+'IsVSyncEnabled',target=settings(q))
    setvs=widget_call(q,'VSyncCheckBox','/Script/UMG.CheckBox.SetIsChecked',InIsChecked=(vs,'ReturnValue'))
    live=q.fn(S+'IsNoArmorCaptureEnabled')
    setdev=widget_call(q,'NoArmorCaptureCheckBox','/Script/UMG.CheckBox.SetIsChecked',InIsChecked=(live,'ReturnValue'))
    can=q.fn(S+'IsDeveloperModeAvailable'); b=q.branch((can,'ReturnValue'))
    show=widget_call(q,'DeveloperGroup',W+'SetVisibility',InVisibility='Visible')
    end=q.set('DraftReady',value=True)
    q.chain(entry(q),ready,setvol,pct,initmode,initquality,initfps,setvs,setdev,b)
    wire(b,'then',show,'execute'); wire(show,'then',end,'execute'); wire(b,'else',end,'execute')
    focus=widget_call(q,'ApplyButton',W+'SetKeyboardFocus'); q.chain(end,focus)
    q.comment('읽기만 하여 초안을 초기화. Construct는 ApplySettings/디버그 값을 변경하지 않음.')

    q=function(bp,'ApplyDraft')
    value=widget_call(q,'VolumeSlider','/Script/UMG.Slider.GetValue')
    setvolume=q.fn(S+'SetMasterVolume',target=settings(q),Volume=(value,'ReturnValue'))
    mode=call_local(q,'ApplyWindowMode');quality=call_local(q,'ApplyQuality');fps=call_local(q,'ApplyFrameLimit')
    checked=widget_call(q,'VSyncCheckBox','/Script/UMG.CheckBox.IsChecked')
    setvs=q.fn(U+'SetVSyncEnabled',target=settings(q),bEnable=(checked,'ReturnValue'))
    apply=q.fn(U+'ApplySettings',target=settings(q),bCheckForCommandLineOverrides=False)
    audio=q.fn(S+'ApplyAudioVolume',target=settings(q))
    feedback=widget_call(q,'SettingsStatus',T+'SetText',InText='적용했습니다.')
    q.chain(entry(q),setvolume,mode,quality,fps,setvs,apply,audio,feedback)
    q.comment('초안 → 기존 엔진 설정 + 저장. 전체 음량은 현재 월드에 적용.')

    q=function(bp,'CloseSettings')
    enable=q.fn(W+'SetIsEnabled',target=q.ref('ParentMenuWidget'),bInIsEnabled=True)
    focus=q.fn(W+'SetKeyboardFocus',target=q.ref('ReturnFocusWidget'))
    remove=q.fn(W+'RemoveFromParent')
    q.chain(entry(q),enable,focus,remove)
    q.comment('초안 폐기 가능. 부모 메뉴 입력과 설정 버튼 포커스를 복구하고 이 오버레이만 닫음.')
    compile_bp(bp)

    eg=BP.get_graph(bp,'EventGraph')
    q=Graph(eg,0,500)
    construct=editor(eg).find_event_node('Construct')
    assert construct and not pin(construct,'then',True).list_connected_pins()
    q.chain(construct,call_local(q,'InitializeDraft'))
    for j,(widget,delegate,func) in enumerate([('VolumeSlider','OnValueChanged','UpdateVolumePercent'),
        ('ApplyButton','OnClicked','ApplyDraft'),('CloseButton','OnClicked','CloseSettings')]):
        progress('binding '+widget)
        ev=event(bp,sw[widget],delegate); ev.set_node_pos(unreal.IntPoint(0,1000+j*400))
        q=Graph(eg,400,1000+j*400); q.chain(ev,call_local(q,func))
        if widget=='VolumeSlider': q.chain(q.nodes[-1],call_local(q,'MarkDraftChanged'))
    for j,widget in enumerate(('WindowModeCombo','QualityCombo','FrameLimitCombo','VSyncCheckBox')):
        progress('binding '+widget)
        delegate='OnCheckStateChanged' if widget=='VSyncCheckBox' else 'OnSelectionChanged'
        ev=event(bp,sw[widget],delegate); ev.set_node_pos(unreal.IntPoint(0,3000+j*300))
        q=Graph(eg,400,3000+j*300);q.chain(ev,call_local(q,'MarkDraftChanged'))
    progress('binding NoArmorCaptureCheckBox')
    ev=event(bp,sw['NoArmorCaptureCheckBox'],'OnCheckStateChanged')
    ev.set_node_pos(unreal.IntPoint(0,2400));q=Graph(eg,400,2400)
    ready=q.get('DraftReady'); availability=q.fn(S+'IsDeveloperModeAvailable')
    both=q.fn(K+'BooleanAND',A=(ready,'DraftReady'),B=(availability,'ReturnValue'))
    b=q.branch((both,'ReturnValue')); setcheat=q.fn(S+'SetNoArmorCaptureEnabled',bEnabled=(ev,'bIsChecked'))
    q.chain(ev,b);wire(b,'then',setcheat,'execute')
    q.comment('개발 빌드에서만, 초기화가 끝난 후 체크 변경을 기존 cvar 래퍼에 즉시 전달.')

    # Optional Escape override omitted: UE's new override graph authoring path
    # crashes before its uncompiled inherited signature can be used safely.
    # Apply and Close remain standard keyboard-focusable buttons.
    progress('compiling complete setting')
    compile_bp(bp)

    progress('appending MainMenu')
    # Append only metadata and missing clicks to the original MainMenu.
    for name in ('ContinueButton','OptionButton','EndButton'):
        ui('ToggleWidgetAsVariable',main_bp,mw[name],True)
    hint=text(main_bp,'ContinueStageHint','저장된 진행이 없습니다.',mw['CanvasPanel_24'],16,MUTED,True)
    hint.set_font(unreal.SlateFontInfo(font_object=AS.load_asset('/Game/Environment/Font/HSBombaram3_0_Thin_Font'),size=18))
    properties(hint,auto_wrap_text=True)
    canvas(hint,(0,0),(0,0),(164.8,810,620,48),2)
    compile_bp(main_bp)
    mg=BP.get_graph(main_bp,'EventGraph');q=Graph(mg,0,4400)
    con=editor(mg).find_event_node('Construct')
    assert con and not pin(con,'then',True).list_connected_pins()
    has=q.fn('/Script/Catrun.CatrunLevelFlowLibrary.HasContinueGame')
    enable=widget_call(q,'ContinueButton',W+'SetIsEnabled',bInIsEnabled=(has,'ReturnValue'))
    saved=q.fn('/Script/Catrun.CatrunLevelFlowLibrary.GetContinueStageLabel')
    labelstr=q.fn('/Script/Engine.KismetTextLibrary.Conv_TextToString',InText=(saved,'ReturnValue'))
    suffix=q.fn('/Script/Engine.KismetStringLibrary.Concat_StrStr',A=(labelstr,'ReturnValue'),B=' 시작부터')
    labeltext=q.fn('/Script/Engine.KismetTextLibrary.Conv_StringToText',InString=(suffix,'ReturnValue'))
    available=q.branch((has,'ReturnValue'))
    hintset=widget_call(q,'ContinueStageHint',T+'SetText',InText=(labeltext,'ReturnValue'))
    emptyhint=widget_call(q,'ContinueStageHint',T+'SetText',InText=(saved,'ReturnValue'))
    q.chain(con,enable,available);wire(available,'then',hintset,'execute');wire(available,'else',emptyhint,'execute')
    q.comment('이어하기 가능 여부와 저장된 스테이지 시작점 표시.')
    ev=event(main_bp,mw['ContinueButton'],'OnClicked');ev.set_node_pos(unreal.IntPoint(0,5000));q=Graph(mg,400,5000)
    resume=q.fn('/Script/Catrun.CatrunLevelFlowLibrary.ContinueGame'); b=q.branch((resume,'ReturnValue'))
    failed=widget_call(q,'ContinueStageHint',T+'SetText',InText='진행을 불러오지 못했습니다. 다시 시도해 주세요.')
    q.chain(ev,resume,b);wire(b,'else',failed,'execute')
    q.comment('여행 요청 성공 뒤에도 메뉴를 유지. 엔진 월드 전환이 제거하며 늦은 실패에도 UI가 남음.')
    ev=event(main_bp,mw['EndButton'],'OnClicked');ev.set_node_pos(unreal.IntPoint(0,5600));q=Graph(mg,400,5600)
    player=q.fn(W+'GetOwningPlayer')
    quitgame=q.fn('/Script/Engine.KismetSystemLibrary.QuitGame',SpecificPlayer=(player,'ReturnValue'),QuitPreference='Quit',bIgnorePlatformRestrictions=False)
    q.chain(ev,quitgame)
    ev=event(main_bp,mw['OptionButton'],'OnClicked');ev.set_node_pos(unreal.IntPoint(0,6200));q=Graph(mg,400,6200)
    create_types=[str(n) for n in q.e.list_available_nodes([]) if str(n).split('|')[-1] in ('CreateWidget','CreateWidget...')]
    assert len(set(create_types))==1, ('CreateWidget candidates',create_types)
    create=q.placed(BP.create_node(mg,create_types[0],unreal.IntPoint(400,6200)))
    literal(create,'Class',bp.generated_class().get_path_name())
    owner=q.fn(W+'GetOwningPlayer');wire(owner,'ReturnValue',create,'OwningPlayer')
    self_types=[str(n) for n in q.e.list_available_nodes([]) if str(n).split('|')[-1].lower() in ('self','self-reference','getareferencetoself')]
    # Native node title is localized; identify its stable node class if the title differs.
    if not self_types:
        self_types=[str(n) for n in q.e.list_available_nodes([]) if str(n).endswith('|자신참조가져오기')]
    assert len(set(self_types))==1, ('Self candidates',self_types)
    selfnode=q.placed(BP.create_node(mg,self_types[0],unreal.IntPoint(600,6500)))
    selfout=[p.name for n in BP.get_node_infos([selfnode]) for p in n.output_pins][0]
    parent=q.set('ParentMenuWidget',source=(selfnode,selfout),cls=bp.generated_class().get_path_name(),target=(create,'ReturnValue'))
    focus=q.set('ReturnFocusWidget',source=q.ref('OptionButton'),cls=bp.generated_class().get_path_name(),target=(create,'ReturnValue'))
    viewport=q.fn('/Script/UMG.UserWidget.AddToViewport',target=(create,'ReturnValue'),ZOrder=100)
    disable=q.fn(W+'SetIsEnabled',bInIsEnabled=False)
    q.chain(ev,create,parent,focus,viewport,disable)
    q.comment('별도 전체 화면 오버레이. 원래 메뉴를 비활성화하여 마우스/키보드 동작을 차단.')
    assert original.issubset({n.get_name() for n in BP.find_nodes(mg)}), 'An original menu node was removed'
    compile_bp(bp);compile_bp(main_bp)
    # No package is saved until both complete widget graphs compile without warnings.
    write_json(OUT/'authored-audit.json',{'settings':audit(bp),'main_menu':audit(main_bp)})
    write_json(OUT/'author-property-schemas.json',PROPERTY_SCHEMAS)
    for asset in (bp,main_bp):
        assert AS.save_loaded_asset(asset,False),asset.get_path_name()
    for assetrow in manifest['assets']:
        file=ROOT/'Content'/(assetrow['asset'].removeprefix('/Game/')+'.uasset')
        assetrow['after_sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
    manifest['complete']=True
    write_json(MANIFEST,manifest)
    print('CATRUN_MENU_AUTHORING_COMPLETE')

try:
    main()
except Exception:
    import traceback
    (OUT/'author-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
    raise
