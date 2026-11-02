# 默认台词：日本語 / English

每种语言有 38 条陪伴台词和 52 条操作回应，共 90 条。JSON / TXT 是原创文本的翻译；当前源码另随附 90 条日语配音，英语配音需自行生成。72 条《温柔回信》为另一个中文文字包。

## 文件

- 日语：[陪伴 JSON](starter-ja-JP.json) / [TXT](starter-ja-JP.txt)、[操作 JSON](operation-ja-JP.json) / [TXT](operation-ja-JP.txt)。
- 英语：[陪伴 JSON](starter-en-US.json) / [TXT](starter-en-US.txt)、[操作 JSON](operation-en-US.json) / [TXT](operation-en-US.txt)。
- 操作规则：[日语](../presets/operation-voice-rules-ja-JP.json)、[英语](../presets/operation-voice-rules-en-US.json)。
- 陪伴互动示例：[日语](../presets/interaction-ja-JP.json)、[英语](../presets/interaction-en-US.json)。

## 导入、生成与播放

1. 从台词库导入需要的 JSON，手动勾选条目，再点击“将勾选台词送到生成页”。JSON 保留分类；TXT 导入会丢失分类，适合阅读、复制。
2. 选择支持目标语言的模型或服务。在可编辑语言下拉框选择 `ja` / `en` 等实际支持代码；参考语言和原文仍按参考录音填写，不要随目标语言盲目更改。
3. 确认生成。原分类会形成子目录，文件仍按“台词-模型名称.wav”命名。若编辑转入文本，将提示改为普通逐行保存，不再套用原分类。
4. 全部日语分类带 `·ja-JP`、英语分类带 `·en-US`，例如 `早晨·ja-JP`、`操作·保存·en-US`。可放在同一根目录，也可按语言分根目录；随机播放根目录时应注意混合语言。
5. 陪伴规则可在台词库选择“新规则分类语言”，再应用分类规则；会确认替换编辑中的规则。也可导入对应语言的互动示例。
6. 操作回应在“设置 → 操作回应规则…”选择语言，点击“快速切换分类”并保存；默认动作一次切换，自定义分类、开关和冷却保留。也可导入规则 JSON。个人音频目录应指向包含分类子目录的根目录。

## 旧分类兼容

旧版陪伴译文没有语言后缀。在台词库使用“更新旧译文分类…”预览后确认并保存。只更新能按稳定来源 ID / 精确原文及原分类识别的默认译文，自定义内容保持原样。原音频不移动或改名；查找已知默认译文时兼容旧子目录，并限定为该语言的默认文本，避免混播中文。

新生成文件使用带后缀的新目录。不要为了升级手动删除旧音频；确认效果后可通过音频库自行整理。

## 默认配音

程序保留中文 90 条，并新增日语 90 条（均为 38 陪伴 + 52 操作），合计 180 条。声音设置里的“随附示例配音语言”控制空个人语音目录的示例；操作回应语言由独立规则决定。中文、英文界面不会自动改变配音语言。已有个人音频优先，缺少英语配音的分类保持静音。

## English

Each language has 38 companion and 52 operation lines. JSON retains categories; TXT does not. Import JSON, check lines and use **Send checked lines to generation**. Select a supported target language while keeping reference language/transcript matched to the recording. Editing transferred text switches to ordinary lines without original categories.

Every default category now ends in **·ja-JP / ·en-US**. Use the category-language selector when applying companion rules, or import the matching interaction preset. In **Operation voice rules**, choose a language, click **Switch categories**, then Save. Custom categories and cooldowns are kept.

For old unsuffixed companion translations, preview **Update legacy translation categories…**. Original audio is not moved; restricted compatibility lookup only matches that language's known default text. New generation uses suffixed directories.

The app includes 90 Chinese and 90 Japanese recordings. English and Gentle Replies remain text requiring your own synthesis/recording. UI language never changes speech language. Personal audio takes priority. Imported text does not start APIs or switch models.

## 日本語

各言語は付き添い台詞 38 件と操作応答 52 件です。JSON を読み込み、必要な行を選んで生成ページに送ります。対象言語は `ja`、参照言語と原文は実際の録音に合わせてください。転送後に文章を編集すると、元の分類を使わない通常生成に切り替わります。

日本語の分類名はすべて `·ja-JP`、英語は `·en-US` で終わります。付き添い規則には言語選択または同梱の設定 JSON を使用します。操作応答は設定の操作規則で日本語を選び、一括切替して保存します。

旧分類は「更新旧译文分类…」で確認してから変更できます。元の音声は移動・改名されず、既知の標準台詞に限って旧フォルダーを参照します。現在のソースには日本語音声 90 件も含まれます。表示言語と音声言語は別々で、個人の音声を優先します。
