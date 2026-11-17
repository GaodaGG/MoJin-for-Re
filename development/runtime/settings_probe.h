/* SPDX-License-Identifier: GPL-3.0-or-later
 * Explicit CLI diagnostics only (double-click startup clears all SR_* flags).
 * Inject into this process's SDL queue, never into the desktop or another app.
 */
static int mojin_settings_probe_mode=-1;
static void mojin_settings_probe_key(SDL_Keycode key, SDL_Scancode scan) {
    SDL_Event e; SDL_zero(e);
    e.type=SDL_EVENT_KEY_DOWN; e.key.windowID=SDL_GetWindowID(s_win);
    e.key.key=key; e.key.scancode=scan; e.key.down=true;
    const int down=SDL_PushEvent(&e);
    e.type=SDL_EVENT_KEY_UP; e.key.down=false;
    const int up=SDL_PushEvent(&e);
    fprintf(stderr,"MOJIN_SETTINGS_PROBE sent_key=%u down=%d up=%d claim=%d text=%d\n",
            key,down,up,s_claim_sink!=NULL,s_text_claim);
}
static void mojin_settings_probe_events(void) {
    static int phase,step;
    static Uint64 started,delay;
    if(mojin_settings_probe_mode<0) {
        const char *v=getenv("SR_MOJIN_SETTINGS_PROBE");
        mojin_settings_probe_mode=v && strcmp(v,"save")==0 ? 2 : v && strcmp(v,"1")==0;
        started=SDL_GetTicks();
        const char *d=getenv("SR_MOJIN_SETTINGS_DELAY_MS");
        unsigned long requested=d?strtoul(d,NULL,10):0;
        delay=requested<=260000?requested:0;
    }
    if(!mojin_settings_probe_mode || !s_win) return;
    Uint64 elapsed=SDL_GetTicks()-started;
    if(elapsed<delay) return;
    elapsed-=delay;
    if(!phase && elapsed>=8000) {
        mojin_settings_probe_key(SDLK_ESCAPE,SDL_SCANCODE_ESCAPE);
        phase=1;
    }
    /* Normal UI navigation: scale 4->3, AA 2->1, output 960x544->1280x720,
     * save, then Esc to the menu and Esc to resume. Never call settings APIs. */
    static const struct { Uint64 at; SDL_Keycode key; SDL_Scancode scan; } steps[]={
        {9000,SDLK_LEFT,SDL_SCANCODE_LEFT},
        {9300,SDLK_DOWN,SDL_SCANCODE_DOWN}, {9600,SDLK_LEFT,SDL_SCANCODE_LEFT},
        {9900,SDLK_DOWN,SDL_SCANCODE_DOWN}, {10200,SDLK_RIGHT,SDL_SCANCODE_RIGHT},
        {10500,SDLK_DOWN,SDL_SCANCODE_DOWN}, {10800,SDLK_DOWN,SDL_SCANCODE_DOWN},
        {11100,SDLK_LEFT,SDL_SCANCODE_LEFT}, {11400,SDLK_LEFT,SDL_SCANCODE_LEFT},
        {11700,SDLK_RETURN,SDL_SCANCODE_RETURN},
        {12400,SDLK_ESCAPE,SDL_SCANCODE_ESCAPE}, {13000,SDLK_ESCAPE,SDL_SCANCODE_ESCAPE},
    };
    if(mojin_settings_probe_mode==2 && phase==1 && s_claim_sink && step<(int)(sizeof(steps)/sizeof(steps[0])) && elapsed>=steps[step].at) {
        mojin_settings_probe_key(steps[step].key,steps[step].scan); step++;
    }
    if(phase==1 && elapsed>=14000) {
        SDL_Event e; SDL_zero(e); e.type=SDL_EVENT_QUIT;
        const int sent=SDL_PushEvent(&e);
        phase=2; fprintf(stderr,"MOJIN_SETTINGS_PROBE sent=quit accepted=%d\n",sent);
    }
}
static void mojin_settings_probe_received(const SDL_Event *e) {
    if(mojin_settings_probe_mode>0 && (e->type==SDL_EVENT_KEY_DOWN || e->type==SDL_EVENT_KEY_UP))
        fprintf(stderr,"MOJIN_SETTINGS_PROBE received=%s key=%u repeat=%d claim=%d text=%d\n",
                e->type==SDL_EVENT_KEY_DOWN?"down":"up",e->key.key,e->key.repeat,
                s_claim_sink!=NULL,s_text_claim);
}
