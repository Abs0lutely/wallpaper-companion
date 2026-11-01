# 默认台词：日语 / English

将项目原有的 **38 条陪伴台词 + 52 条操作回应**分别翻译为日语与英语，每种语言共 90 条，保留温柔、自然的日常语气。均为项目原创文本的翻译，可按 MIT 许可使用、修改与分享；不含游戏原台词、参考音频或新生成的配音。

| 用途 / Purpose | 日本語 | English |
| --- | --- | --- |
| 陪伴台词：38 条 / Companion lines: 38 | [starter-ja-JP.json](starter-ja-JP.json) · [TXT](starter-ja-JP.txt) | [starter-en-US.json](starter-en-US.json) · [TXT](starter-en-US.txt) |
| 操作回应：52 条 / Operation responses: 52 | [operation-ja-JP.json](operation-ja-JP.json) · [TXT](operation-ja-JP.txt) | [operation-en-US.json](operation-en-US.json) · [TXT](operation-en-US.txt) |
| 对应操作规则：26 类 / Matching operation rules: 26 events | [日语规则](../presets/operation-voice-rules-ja-JP.json) | [English rules](../presets/operation-voice-rules-en-US.json) |

## 导入与生成

1. 在“台词库 → 导入台词 JSON / TXT”选择需要的 **JSON**。导入会追加并按分类与文本去重，不会替换已有中文内容；生成勾选仍由用户选择。
2. 选择要生成的台词，点击“将勾选台词送到生成页”。JSON 保留分类；TXT 适合查看和复制，直接导入 TXT 会统一归到“点击回应”，丢失原有分类。
3. 选择支持目标语言的模型或第三方音色，设置目标语言。GPT-SoVITS 通常使用 `ja`（日语）或 `en`（英语），请以实际 API 支持的语言代码为准；Azure 选择对应 `ja-JP` / `en-US` 音色与区域。**参考语言及逐字原文仍按实际参考音频填写，不要随目标语言盲目更改。**
4. 选择独立的语言输出根目录，例如 `<共享语音目录>/ja-JP` 或 `<共享语音目录>/en-US`，生成时按分类保存。输出仍采用“台词-模型名称.wav”；对效果逐条试听，跨语言效果取决于模型。

这些文件不会自动生成音频、启动 API、改动模型或切换软件语言。现有安装版即可导入，无需为下载台词重新安装软件。

## 陪伴分类与播放

陪伴台词保留中文分类名，以兼容现有“应用分类触发规则”。将壁纸语音目录设为上一步语言根目录，已有规则即可寻找对应子目录。若把不同语言生成到同一目录，随机播放可能混用语言，因此推荐分开存放。

| 保留的目录名 | English meaning | 日本語 |
| --- | --- | --- |
| 点击回应 | Click response | クリックへの返事 |
| 返回桌面 | Welcome back | おかえりの挨拶 |
| 早晨 | Morning | 朝 |
| 白天 | Daytime | 昼間 |
| 夜间 | Night | 夜 |
| 闲置陪伴 | Quiet company | 静かなひととき |

## 操作回应如何使用

操作台词分类使用 `操作·保存·ja-JP` / `操作·保存·en-US` 等带语言后缀的目录名，避免被程序内置的中文台词文件名筛选忽略。

生成完成后，在“设置 → 操作回应规则…”导入对应语言规则并保存；将“操作回应语音目录”选择为**包含这些分类子目录的语言根目录**。规则文件不含本机路径或密钥，可先导出现有规则留作备份。要恢复中文，可在操作规则中恢复默认规则，再选择原语音目录。

这份规则只调整操作回应分类，不替换壁纸互动规则；仍有 26 类动作、每类两句，冷却和默认总开关与原规则一致。

## English quick start

These are translations of the app's **38 default companion lines and 52 operation responses**, not the separate 72-line Gentle Replies pack. They are text resources, not synthesized recordings. The interface remains primarily Chinese.

1. Import a **JSON** file through **台词库 → 导入台词 JSON / TXT**. Imports append and deduplicate; existing Chinese entries are kept. TXT is convenient for reading, but importing TXT loses the original categories.
2. Select the imported lines and choose **将勾选台词送到生成页**. Select a model/voice that supports the target language, then set the target-language field. The reference transcript and reference language must still match the actual reference recording.
3. Generate to a separate language root, such as `<shared voice folder>/en-US`, keeping category subfolders. For wallpaper interactions, point the profile's voice folder to that root. Companion category names intentionally remain in Chinese to work with existing category-based rules; see the table above.
4. For operation responses, also import `operation-voice-rules-en-US.json` in **设置 → 操作回应规则…**, save it, and set **操作回应语音目录** to the language root containing the generated operation-category subfolders. Japanese works the same way with the `ja-JP` files. Export your existing operation rules first if you want a backup.

The packs contain no credentials or absolute paths. Importing does not start a speech API, switch models, or change the UI language. Use separate language folders to avoid mixed-language random playback. Preview generated results; cross-language quality depends on the model.

## 日本語の使い方

この台詞集は、標準の付き添い台詞 38 件と操作への返事 52 件を翻訳したものです。音声ファイルは含まれていません。別配布の中国語台詞集「温柔回信」72 件とは異なります。

「台词库 → 导入台词 JSON / TXT」で日本語の JSON を読み込み、生成したい台詞を選んで「将勾选台词送到生成页」を押してください。日本語に対応したモデル・音声を選び、生成対象の言語を設定します。参照音声の言語と原文は、その音声に正確に合わせてください。

出力先は日本語専用の親フォルダーにすると便利です。通常の付き添い台詞は、既存の規則と互換性を保つため、分類フォルダー名を中国語のままにしています。壁紙の語音フォルダーを、この親フォルダーに指定してください。

操作への返事を使う場合は、「设置 → 操作回应规则…」で日本語用の規則 JSON も読み込んで保存し、「操作回应语音目录」に分類フォルダーが入っている親フォルダーを指定します。必要に応じて、変更前の規則を書き出して保管してください。

読み込むだけでは音声生成やモデルの切り替えは行われません。画面の表示言語も変わりません。生成後は実際に試聴して、発音や声の雰囲気を確認してください。
