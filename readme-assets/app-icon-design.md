# 壁纸声伴图标

采用用户提供的粉发、樱花、玫瑰金耳机少女画面作视觉参考，通过内置 imagegen 工具重新生成方形头像图标。保留温暖夕阳、侧编发和耳机的特征，与二次元壁纸及语音陪伴的定位对应。参考原图和未采用的候选图不纳入分发。

- `app-icon.png`：生成图像母版，保留原始透明通道。
- `app-icon.ico`：16 / 20 / 24 / 32 / 40 / 48 / 64 / 128 / 256 像素，共九档 PNG 帧。
- `scripts/prepare_app_icon.py`：从批准的 PNG 缩放并编码 ICO，不重新绘画、不改变内容。命令：`.\.conda\python.exe scripts/prepare_app_icon.py`。

窗口、应用对话框与托盘从此处读取图标；正式构建把同一个 ICO 复制到 `build/app.ico`，供 PyInstaller 和 Inno Setup 使用。readme-assets 随发行包和便携更新器一起分发。已有安装版不因源码更新而自动替换图标；后续新包重新构建后才会更新 EXE/安装包资源。

## 最终生成提示词

```text
Use case: logo-brand. Asset type: FINAL square Windows desktop application icon for 壁纸声伴 / Wallpaper Companion, based on the provided reference image. Image 1 is the visual/character reference, not a backdrop to paste wholesale. Re-illustrate the SAME recognizable anime young adult woman: long rose-pink hair with the small side braid, dusky pink-violet eyes, blossom-and-ribbon hair accessory, rose-gold over-ear headphones resting around her neck, gentle warm expression and chin resting lightly on one hand, cream clothing with dusty-rose sleeve. Preserve her identity, hairstyle and palette, but simplify fine details for an app icon. Compose an extremely clear face-dominant close-up portrait centered within a rounded-square tile: face and hair around 65 percent of tile, both headphone earcups clearly visible near the bottom, just shoulders rather than full body, enough padding around head/accessory. Behind her only a simplified warm peach-to-mauve sunset glow and a small subtle wallpaper-window frame silhouette, with one or two stylized cherry blossoms near the corner. This combines a beautiful anime wallpaper character and a voice/audio companion. Make an elegant premium anime illustration with cleaner, slightly bolder contours and stronger separation than the reference so it remains recognizable at 32/48px. Rich warm dusty pinks, rose gold, cream and deep plum edge tones; no washed-out low-contrast haze. No added text, letters, watermark, generic equalizer badge, music note, full cityscape, extra characters, icon grid, flat stock logo, photorealism, sexualized framing, excessive tiny blossoms or external drop shadows. ONE standalone square app icon, rounded tile occupies about 92 percent of the canvas. Actual transparent alpha outside the rounded-square icon; do not paint a checkerboard or black background.
```
