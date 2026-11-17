/* SPDX-License-Identifier: GPL-3.0-or-later
 * Included after the pinned overlay's row layout helpers. No SDL or file I/O.
 */
#include "graphics_settings.h"

#define MOJIN_Q_ID(n) NK_OVERLAY_ID(0x000900u + (n))
static void mojin_choice_row(NkUi *ui, unsigned row, const char *label,
                             const char *description, float width,
                             NkOverlayAction *result) {
    NkUiId id = MOJIN_Q_ID(1u + row * 32u);
    char value[160];
    mojin_graphics_choice((int)row,value,sizeof(value));
    bool focused = nk_ui_button_focused(ui,id);
    NkUiNavDir dir = NK_UI_DIR_NONE;
    if(row_begin(ui,id,row,label,description,width - 280.0f,true)) {
        nk_ui_text_role(ui,part_id(row,3u),nk_ui_frame_text(ui,value),NK_UI_TYPE_BODY_S,nk_ui_theme(ui)->paper);
        nk_ui_end_container(ui);
    }
    int step=0;
    if(focused && nk_ui_take_event(ui,NK_UI_EV_NAV,&dir)) {
        if(dir==NK_UI_DIR_LEFT) step=-1;
        if(dir==NK_UI_DIR_RIGHT) step=1;
    } else if(nk_ui_take_activation(ui,id)) step=1;
    if(step) *result=nk_overlay_action((NkOverlayActionKind)(MOJIN_GRAPHICS_ACTION_BASE+row),step);
}

NkOverlayAction nk_overlay_page_settings(NkUi *ui,NkOverlayState *state,const NkOverlayModel *model) {
    static const NkUiPromptItem prompts[]={
        {NK_UI_PROMPT_ACT_MOVE,"选择"},{NK_UI_PROMPT_ACT_CONFIRM,"更改"},{NK_UI_PROMPT_ACT_BACK,"返回"}};
    const NkUiTheme *theme=nk_ui_theme(ui);
    const MojinGraphicsView *v=mojin_graphics_view();
    NkOverlayAction result=nk_overlay_action(NK_OVERLAY_ACT_NONE,0);
    float inner=nk_overlay_page_begin(ui,model,880.0f);
    if(inner<=0) return result;
    nk_overlay_eyebrow(ui,QUICK_ID_EYEBROW,NULL,"游戏已暂停",theme->muted);
    nk_ui_text_role(ui,QUICK_ID_TITLE,"画质设置",NK_UI_TYPE_TITLE,theme->paper);
    char current[256],next[256];
    snprintf(current,sizeof(current),"当前场景目标 %d × %d   ·   合成 %d × %d   ·   窗口输出 %d × %d",
        v->scene_width,v->scene_height,v->composition_width,v->composition_height,v->output_width,v->output_height);
    NkUiTextStyle note=nk_ui_type(NK_UI_TYPE_FOOTNOTE,theme->muted); note.wrap=true;
    nk_ui_text(ui,MOJIN_Q_ID(0x200u),nk_ui_frame_text(ui,current),&note);
    snprintf(next,sizeof(next),"下次请求场景目标 %d × %d；原始贴图、HUD 和影片不会因此增加细节。",
        480*v->pending.scale*v->pending.ssaa,272*v->pending.scale*v->pending.ssaa);
    nk_ui_text(ui,MOJIN_Q_ID(0x201u),nk_ui_frame_text(ui,next),&note);
    NkUiLayout rows=nk_overlay_layout(NK_UI_LAYOUT_COLUMN,nk_overlay_grow(),nk_overlay_fit(),2.0f);
    if(nk_ui_begin_container(ui,QUICK_ID_ROWS,&rows,NULL)) {
        mojin_choice_row(ui,MOJIN_GRAPHICS_SCALE,"合成分辨率","更高分辨率会增加显卡负担。",inner,&result);
        mojin_choice_row(ui,MOJIN_GRAPHICS_AA,"抗锯齿","场景超采样后缩小到合成分辨率。",inner,&result);
        mojin_choice_row(ui,MOJIN_GRAPHICS_WINDOW,"窗口分辨率","受屏幕限制；放大窗口不提高场景细节。",inner,&result);
        mojin_choice_row(ui,MOJIN_GRAPHICS_FULLSCREEN,"显示模式","全屏使用桌面实际分辨率。",inner,&result);
        nk_ui_end_container(ui);
    }
    note.rgba=v->dirty ? theme->warning : theme->muted;
    nk_ui_text(ui,MOJIN_Q_ID(0x202u),v->status,&note);
    note.rgba=theme->muted;
    nk_ui_text(ui,QUICK_ID_FOOT,"当前保持原作速度；90 / 120 FPS 尚未验证，未启用。",&note);
    NkUiLayout actions=nk_overlay_layout(NK_UI_LAYOUT_ROW,nk_overlay_grow(),nk_overlay_fit(),12.0f);
    if(nk_ui_begin_container(ui,MOJIN_Q_ID(0x203u),&actions,NULL)) {
        if(nk_ui_button(ui,MOJIN_Q_ID(0x220u),"保存，下次启动生效",0u))
            result=nk_overlay_action((NkOverlayActionKind)MOJIN_GRAPHICS_ACTION_SAVE,0);
        if(nk_ui_button(ui,MOJIN_Q_ID(0x221u),"撤销选择",0u))
            result=nk_overlay_action((NkOverlayActionKind)MOJIN_GRAPHICS_ACTION_RESET,0);
        if(nk_ui_button(ui,NK_OVERLAY_ID_SETTINGS_BACK,"游戏菜单",0u))
            nk_overlay_go(state,NK_OVERLAY_SCREEN_MENU,NK_OVERLAY_ID_SETTINGS);
        nk_ui_end_container(ui);
    }
    if(nk_ui_take_event(ui,NK_UI_EV_BACK,NULL))
        nk_overlay_go(state,NK_OVERLAY_SCREEN_MENU,NK_OVERLAY_ID_SETTINGS);
    nk_overlay_page_end(ui,"左右切换档位",prompts,sizeof(prompts)/sizeof(prompts[0]));
    return result;
}
