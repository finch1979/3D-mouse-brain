# DeepSeek 唯讀稽核報告：九個小鼠系統頁面

稽核對象：`auditory / somatosensory / gustatory / vestibular / cerebellum / limbic / pain / sleep / autonomic`
範圍：雙語一致性、連結目的地、導覽分組、控制項措辭。
本報告為靜態原始碼與既有產物比對；**未執行** Playwright／建置／部署，未連網。

## 檔案變更

- 新增：`.agents/dp_result.md`（本報告）
- 未修改任何原始碼、資料、mesh、既有 HTML、`project_tree.txt`、`human/`、`web/lib/`、`external/` 或 `C:` 副本。

## 執行過的指令（皆唯讀）

- `read`：`systems.py`、`adult_system.py`、`systems.json`、`build_mouse.py`、`hub_design.py`、`navigation_map.py`、`viewer_upgrade.py`、`templates/mouse.css`、`templates/scene.js`、`render/viewer_template.py`、`render/viewer_template.html`（重點段落）、`bake_meshes.py`、`tests/check_mouse_systems_ui.py`、`tests/test_mouse_systems.py`、`docs/architecture/mouse-systems-evidence.md`。
- `git status --short`、`git log --oneline -5`、`git show --stat 744f050`、`git show 744f050 -- site/build_mouse.py site/hub_design.py site/README.md tests/README.md scripts/mouse_systems.py`。
- `rg`（目標字串搜尋，避免讀取 base64 blob）：`MNI152`、`human`、`人類`、`coronal slice`、`head shell`、`頭部大小示意`、`ANATOMICAL VIEW / 01`、`MATERIAL / ANNOTATION`、`hotspot`、`data-target`。
- `py -3.13 -c`（僅記憶體運算，不寫檔）：
  - 以 `runpy` 載入 `systems.py`，驗證 9 系統所有 `regions` 皆在 `REGION_ZH`（42 鍵）、所有 branch 節點可解析（population 或 `region_side`）。
  - 比對 branch `refs` 與 evidence ledger（19 個 ID）、`regions` 與 `P56/mesh/manifest.json`（44 鍵，含 `root`）。
  - 從 9 個生成 HTML 抽出 `const STRINGS`／`const LABELS`，檢查 zh/en 是否皆非空。
  - 解析 `site/dist/mouse/index.html`，列出各卡片／導覽連結目的地是否存在、各 group 卡片與 map-section 標籤。
- `Test-Path`：確認 9 個來源 HTML、3 個 PATHWAYS HTML、2 個 related 目標、以及 dist 目標檔存在。

## 檢查結果

- 通過（靜態）：
  - 9 系統 `regions` 全部有中文名；所有 branch 節點可解析；`refs` 全在 evidence ledger；所需 mesh 全在 manifest。
  - 9 個生成頁面的 `STRINGS`／`LABELS` 除刻意的空 `title_suffix` 外，無缺 zh 或缺 en。
  - `systems.json` 與 `systems.py` 的 name/short/route/fact 一致；group 值皆為 `pathways/structures/output`。
  - 9 個 hub 卡片與導覽連結在 `site/dist` 皆存在；`related` 連結（somatosensory → `/mouse/whisker/`、limbic → `/mouse/P56/hippocampus_3d.html`）目標皆存在。
  - 9 頁皆含 Allen／Finch／醫療免責字樣與來源連結（`https://` 出現 10 次）。
- 失敗：無（本次靜態檢查未出現硬性失敗；下列為內容／一致性缺陷，非檢查腳本失敗）。
- 略過：`tests/check_mouse_systems_ui.py`、`tests/test_mouse_systems.py`、任何建置或瀏覽器渲染驗證（依契約不執行；不可聲稱已跑測試）。

## 具體發現（依嚴重度）

### F1（中）structures 分組說明已過時，與新成員不符
- 位置：`site/build_mouse.py:150-151`（`GROUPS` 的 `structures` 副標）；成員來源 `site/build_mouse.py:142-144`。
- 內容：`structures` 副標仍為「經典檢視器,P56 / P15 / P14」／"the classic viewers, P56 / P15 / P14"，但該組已新增 `cerebellum`、`limbic`、`sleep` 三個非「經典檢視器」的新頁。
- 重現：`py -3.13 -c` 解析 `site/dist/mouse/index.html` 的 `system-group` 區塊，得 `structures -> [...,'cerebellum','limbic','sleep']`，同區塊 `data-en="the classic viewers, P56 / P15 / P14"`。屬已上線產物可見的敘述不一致。

### F2（中）同一 group 在 hub 卡片與導覽地圖使用不同中英標籤
- 位置：`site/build_mouse.py:147-153`（hub `GROUPS`）對 `site/navigation_map.py:21-25`（map groups）。
- 內容：
  - `pathways`：hub＝「感覺路徑 / Pathways」；map＝「感覺入口 / Sensory entry points」。
  - `structures`：hub＝「結構與切片 / Structures &amp; plates」；map＝「腦內結構 / Within the brain」。
  - `output`：兩者一致「身體連結 / Brain &amp; body」。
- 重現：解析 dist hub 的 `map-section` 標籤得「腦內結構/Within the brain」「感覺入口/Sensory entry points」「身體連結/Brain &amp; body」，與卡片 `group-heading` 的「感覺路徑/Pathways」「結構與切片/Structures &amp; plates」不同。另 hub 區塊順序為 pathways→structures→output，map 為 structures→pathways→output。

### F3（中）九頁共用說明含人類專屬「頭部外殼」措辭
- 位置：`site/templates/scene.js:277`（`explanation` 文案，經 `viewer_upgrade.py` 注入並在 `mount()` 掛入 `#naPane-layers`）。
- 內容：文案含「頭部大小示意預設隱藏」／"the approximate head shell starts hidden"。小鼠九頁沒有 skull／頭部 mesh：`adult_system.py:35` 只載入 `root`＋各區，`P56/mesh/manifest.json` 無 `skull`；同一面板的滑桿卻稱「腦表面輪廓／Brain surface」（`scene.js:272`）。同一面板內兩種物種敘述互相矛盾。
- 重現：`rg -c "head shell"` 對 9 個 `site/dist/mouse/<slug>/index.html` 皆為 1；`scene.js` 的 `display` 無條件掛入 layers pane。建議以瀏覽器在 zh/en 兩語開 Layers 面板確認可見性（靜態已可證字串存在且被掛載）。

### F4（低）裝飾性 kicker 未雙語
- 位置：`site/templates/scene.js:109`（`ANATOMICAL VIEW / 01`）與 `scene.js:269`（`MATERIAL / ANNOTATION`）為硬編碼英文，未走 `text(zh,en)`。
- 重現：`rg -c "ANATOMICAL VIEW / 01"`、`rg -c "MATERIAL / ANNOTATION"` 對 9 頁皆為 1，且兩者在 zh 模式不會被 `translate()` 更新。

### F5（低）小鼠 render 模組殘留人類導向註解／docstring（非使用者可見）
- 位置：
  - `mouse/src/mouse_atlas/render/viewer_template.py:1-14`：docstring 稱此模板供「six new human system pages」使用，並指向 `build/human_*.py`。
  - `mouse/src/mouse_atlas/render/viewer_template.html:303-304`：JS 註解寫 `MNI152 RAS` 與 `brain + cord where present`。
  - `mouse/src/mouse_atlas/render/bake_meshes.py:3`：指向 `outputs/human/limbic/human_limbic_3d.html`。
- 重現：9 頁生成 HTML 內皆含 `MNI152` 與 `coronal slice` 字串（`rg -o` 各 1 次），來源即上述註解；座標慣例（RAS）本身正確，僅物種標示錯誤。這些是註解／文件，不會顯示給讀者。

### F6（低）新系統 `hotspot` 語意與其他條目不一致
- 位置：`adult_system.py:116` 將 `hotspot=slug`（如 `auditory`），而 `build_mouse.py` 其他條目用解剖位置（`eye/whisker/nose/motor/hippocampus`）。
- 影響：`navigation_map.py:30` 目前只判斷真值，故無立即錯誤；但欄位語意已被改變，若未來沿用 hotspot 做定位會誤用。

### F7（資訊）導覽編號在同一分組內不連續
- 位置：全域序號由 `hub_design.py:43` `enumerate(systems)` 決定，map 沿用同一 `index+1`（`navigation_map.py:37`）。
- 現象（由 dist 解析）：感覺入口 01,02,03,11,12,13,14；腦內結構 04,06,15,16,18；身體連結 17,19。卡片與 map 編號一致（測試僅檢查此一致性），但分組內跳號。屬設計取捨，非硬性錯誤。

### F8（資訊）`title_suffix` 刻意為空
- 位置：`adult_system.py:62` `bi('','')`。因 `title_main` 已含「（小鼠）／(mouse)」，判定為刻意設計，非缺翻譯。

## 需瀏覽器確認的項目

- F3、F4 的最終可見性與換語言後是否更新（本報告只證明字串存在且被掛載，未跑 Chromium）。
- F7 的實際閱讀體驗（需人工判斷是否要調整分組排序或重編號）。

## 假設

- `site/dist/` 為 `744f050` 加入九系統、`b9122f5` 修復後的現行產物；`systems.json` 與生成 HTML 同步。
- `P56/mesh/manifest.json` 的 44 鍵即為九系統可用 mesh 全集；`root` 為全腦外殼，小鼠頁無 skull。
- evidence ledger 19 個 ID 為引用全集。

## 資料安全聲明

全程唯讀：未改動任何原始碼、原始 mesh／data、生成 HTML、`project_tree.txt`、`human/`、`web/lib/`、`external/` 或 `C:` 副本；未執行 fetch／build／deploy；未做任何 git 變更；未安裝套件、未連網、未接觸憑證。唯一寫入為本檔 `.agents/dp_result.md`。

## 注意到的無關變更

- `git status --short` 顯示：` M .agents/current_task.md`、`?? .agents/code-router-install-completed.md`、`?? project_tree.txt`。這些在本次稽核前即存在，非本次產生，亦未觸碰。

## 優先順序清單

1. F1：更新 `site/build_mouse.py:150-151` 的 `structures` 副標，使其涵蓋新系統（或把新系統改置於語意相符的分組）。
2. F2：統一 `build_mouse.py` 與 `navigation_map.py` 的 group 標籤與順序（單一來源），避免同一分組出現兩套中英名稱。
3. F3：修正 `scene.js:277` 對小鼠頁的人類「頭部外殼」措辭（改為腦表面／依物種切換）。
4. F4：將 `scene.js:109,269` 的裝飾 kicker 改走雙語函式。
5. F5：更新小鼠 render 模組 docstring／註解，移除 `MNI152`、`human`、`human_limbic` 等物種錯置描述（不影響輸出）。
6. F6：讓新系統 `hotspot` 語意一致（真值旗標或實際解剖位置二擇一並註明）。
7. F7：若在意閱讀動線，考慮分組內重新編號或依分組排序再編號。

**可行動問題：有。** 最值得先處理者為 F1、F2（已上線可見的分組敘述與標籤不一致）與 F3（九頁使用者可見的人類專屬措辭）。
