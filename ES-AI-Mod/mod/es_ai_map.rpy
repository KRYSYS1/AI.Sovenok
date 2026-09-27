# -*- coding: utf-8 -*-
# AI Совёнок — иллюстрированная карта лагеря.
#
# Подложка — настоящая карта лагеря с фандом-вики Бесконечного лета
# (everlasting-summer.fandom.com, лицензия CC-BY-SA). Картинка не может быть
# передана по текстовому мосту как бинарник, поэтому она лежит рядом в виде
# base64-текста (es_ai_map_bg.b64) и раскодируется в память на старте через
# im.Data — это обходит индекс загрузчика Ren'Py (loose-файл не нужен в архиве).
#
# По просьбе пользователя: просто иллюстрированная карта как на вики, с зумом и
# перетаскиванием, БЕЗ всплывающих окон (попапов) по клику.

init python:
    ES_AI_MAP_IMG_W = 1178.0
    ES_AI_MAP_IMG_H = 663.0
    ES_AI_MAP_BG_NAME = "es_ai_camp_map"

    # Пиксельные координаты локаций на подложке 1178x663 (центр значка).
    # Сняты по сетке с реальной карты; для маркера «вы здесь».
    ES_AI_MAP_PIN = {
        "square": (588, 280),
        "camp_gate": (283, 300),
        "gate_no_bus": (210, 292),
        "bus_gate": (150, 285),
        "bus_inside": (120, 280),
        "bus_stop": (90, 275),
        "road": (110, 288),
        "houses": (450, 345),
        "dv_house_ext": (600, 128), "dv_room": (600, 128),
        "sl_house_ext": (450, 405), "sl_room": (450, 405),
        "un_house_ext": (430, 445), "un_room": (430, 445),
        "mt_house_ext": (512, 245), "mt_room": (512, 245),
        "semen_room": (560, 152),
        "dining_ext": (660, 322), "dining": (660, 322),
        "clubs": (355, 288), "club_room": (355, 288),
        "musclub": (400, 190), "musclub_inside": (400, 190),
        "library": (748, 195),
        "stage": (680, 58), "stage_big": (680, 58),
        "playground": (850, 315),
        "aidpost": (660, 237), "aidpost_inside": (660, 237),
        "path": (400, 112),
        "polyana": (300, 92),
        "washstand": (460, 297),
        "beach": (820, 455),
        "island": (400, 600),
        "boathouse": (547, 517),
        "bathhouse": (500, 470),
        "old_building": (177, 615),
        "catacombs": (205, 598),
        "mine": (235, 582),
    }

    def es_ai_load_map_bg():
        """Раскодировать base64-подложку и зарегистрировать как image.

        Подложка лежит рядом кусками es_ai_map_bg.b64.part0, .part1, ...
        (мост к ПК не пропускает большие файлы одним куском). Читаем части по
        порядку, склеиваем, декодируем и оборачиваем в im.Data — без записи на
        диск и без индекса загрузчика Ren'Py. Безопасно вызывать повторно."""
        import os, base64
        if renpy.has_image(ES_AI_MAP_BG_NAME):
            return True
        dirs = []
        try:
            dirs.append(ES_AI_MOD_DIR)
        except Exception:
            pass
        try:
            dirs.append(os.path.join(renpy.config.gamedir, "mods", "es_ai"))
        except Exception:
            pass
        try:
            dirs.append(os.path.join(renpy.config.basedir, "game", "mods", "es_ai"))
        except Exception:
            pass
        for d in dirs:
            try:
                # single-file вариант (на будущее), иначе — части
                single = os.path.join(d, "es_ai_map_bg.b64")
                b64 = ""
                if os.path.exists(single):
                    with open(single, "r") as f:
                        b64 = f.read()
                else:
                    i = 0
                    got = False
                    while True:
                        p = os.path.join(d, "es_ai_map_bg.b64.part%d" % i)
                        if not os.path.exists(p):
                            break
                        with open(p, "r") as f:
                            b64 += f.read().strip()
                        got = True
                        i += 1
                    if not got:
                        continue
                if not b64:
                    continue
                raw = base64.b64decode(b64)
                renpy.image(ES_AI_MAP_BG_NAME, im.Data(raw, "es_ai_map_bg.jpg"))
                return True
            except Exception as e:
                try:
                    renpy.log("es_ai: map bg load failed (%s): %s" % (d, e))
                except Exception:
                    pass
        return False

    # Пытаемся загрузить сразу на старте (если не выйдет — попробуем при показе).
    ES_AI_MAP_BG_OK = es_ai_load_map_bg()


screen es_ai_map():
    modal True
    zorder 250
    default es_ai_map_zoom = 1.0

    add Solid("#000000ee")

    python:
        _ok = ES_AI_MAP_BG_OK or es_ai_load_map_bg()
        _imgw, _imgh = ES_AI_MAP_IMG_W, ES_AI_MAP_IMG_H
        _availw = int(config.screen_width - 80)
        _availh = int(config.screen_height - 170)
        _base = min(_availw / _imgw, _availh / _imgh)
        if _base <= 0:
            _base = 0.5
        _sc = _base * es_ai_map_zoom
        _dw = int(_imgw * _sc)
        _dh = int(_imgh * _sc)
        _curloc = ES_AI_LOC_CUR[0]
        _pin = ES_AI_MAP_PIN.get(_curloc)
        _pinx = int(_pin[0] * _sc) if _pin else 0
        _piny = int(_pin[1] * _sc) if _pin else 0
        _curname = ES_AI_LOCATION_INDEX.get(_curloc, {}).get("name", u"")

    frame:
        xalign 0.5
        yalign 0.5
        background Frame("#0d1117f4", 10, 10)
        padding (16, 14)
        vbox:
            spacing 10
            hbox:
                spacing 16
                text "🗺 Карта лагеря «Совёнок»" size 28 color "#ffd479"
                if _curname:
                    text ("● вы здесь: %s" % _curname) size 17 color "#ff6b6b" yalign 0.8
                else:
                    text "колёсико / кнопки — зум, тяни мышью — двигать" size 16 color "#8a97a6" yalign 0.8

            # ------- сама карта в области с прокруткой/перетаскиванием -------
            frame:
                xsize _availw + 4
                ysize _availh + 4
                background Solid("#1b232e")
                if _ok:
                    viewport id "es_ai_mapvp":
                        draggable True
                        mousewheel True
                        edgescroll (30, 800)
                        xsize _availw
                        ysize _availh
                        fixed:
                            xysize (_dw, _dh)
                            add ES_AI_MAP_BG_NAME:
                                zoom _sc
                            if _pin:
                                text "●":
                                    xpos _pinx
                                    ypos _piny
                                    xanchor 0.5
                                    yanchor 0.5
                                    size 30
                                    color "#e12d2d"
                                    outlines [(3, "#ffffff", 0, 0)]
                                text "Вы здесь":
                                    xpos _pinx
                                    ypos (_piny - 22)
                                    xanchor 0.5
                                    yanchor 1.0
                                    size 16
                                    color "#ffffff"
                                    outlines [(2, "#000000", 0, 0)]
                else:
                    text "Не удалось загрузить изображение карты.\nПроверь файл mods/es_ai/es_ai_map_bg.b64" :
                        align (0.5, 0.5)
                        size 20
                        color "#e59ab6"
                        text_align 0.5

            # ------- нижняя панель: зум и закрытие -------
            hbox:
                spacing 12
                yalign 1.0
                text "Карта © фандом-вики ЕЛ, CC-BY-SA" size 14 color "#5f6b78" yalign 0.5
                null width 20
                textbutton "−" action SetScreenVariable("es_ai_map_zoom", max(0.5, es_ai_map_zoom - 0.25))
                text ("%d%%" % int(es_ai_map_zoom * 100)) size 18 color "#d7dee6" yalign 0.5 xsize 70 text_align 0.5
                textbutton "+" action SetScreenVariable("es_ai_map_zoom", min(4.0, es_ai_map_zoom + 0.25))
                textbutton "Сброс" action SetScreenVariable("es_ai_map_zoom", 1.0)
                null width 30
                text "Esc — закрыть" size 15 color "#777777" yalign 0.5
                textbutton "Готово" action Hide("es_ai_map")

    key "game_menu" action Hide("es_ai_map")
