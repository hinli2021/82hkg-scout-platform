# 第4項測驗套件｜認識世界及香港童軍運動發展

本套件保留原有第 4 項獨立測驗的題庫與合格線，供參考及移植；**現行平台的遊戲 1（童軍歷史山洞）只重用這 50 題，不採用本套件的 80 分合格線**。走到山洞終點並完成全部題目即通關，分數只供回顧。程式不依賴第三方函式庫。

## 套件內容

- `question-bank.json`：題目、選項、部分分類及顯示資料；不含正確答案索引。
- `answer-key.json`：正確答案索引、答案解說及領袖核實提示。若考核須保密，請只存放在伺服器或平台的私有區域。
- `quiz-engine.js`：建立隨機選項的作答版本、計分及產生錯題檢討；支援瀏覽器全域變數與 Node.js CommonJS。
- `preview.html`：可離線開啟的獨立互動示範。示範頁為方便操作，會在瀏覽器端載入答案鍵，適合練習及檢視，不適合用作保密的正式考核。
- `test.js`：使用 Node.js 內建測試模組檢查題數、分部、計分及合格線。

## 題目與計分

- 共50題：甲部「世界童軍運動」15題、乙部「香港童軍運動」15題、丙部「童軍常識＋82旅」20題。
- 每題2分，滿分100分，80分合格。
- 預設依甲、乙、丙部排列題目；每次作答會隨機排列各題選項。
- 支援不限時、30分鐘或40分鐘。未作答題目不計分；提交後可檢視答案及解說。
- 可以只選部分題目。引擎會按設定的合格百分比計算部分測驗合格線；例如30題、每題2分，80%合格線為48/60。若平台有不同規則，可在建立作答時明確指定 `passScore`。

## Node.js 整合範例

```js
const bank = require("./question-bank.json");
const key = require("./answer-key.json");
const Item4QuizEngine = require("./quiz-engine.js");

const attempt = Item4QuizEngine.createAttempt(bank, key, {
  shuffleQuestions: false,
  shuffleOptions: true
});

// 網頁只應接收 attempt.quiz；將 attempt.answerKey 留在伺服器。
const questionsForBrowser = attempt.quiz;

// responses 格式：{ "甲1": 2, "甲2": 0 }；數字代表畫面上選項的索引，從0開始。
const result = Item4QuizEngine.gradeAttempt(attempt, responses);
console.log(result.score, result.maxScore, result.passed, result.sections);
```

### 只測甲、乙兩部

```js
const attempt = Item4QuizEngine.createAttempt(bank, key, {
  parts: ["world", "hk"],
  shuffleOptions: true
});
```

### 選取題數或自訂合格分數

```js
const attempt = Item4QuizEngine.createAttempt(bank, key, {
  questionCount: 30,
  shuffleQuestions: true,
  shuffleOptions: true,
  passScore: 48
});
```

## 瀏覽器端整合

在整合平台載入 `quiz-engine.js` 後，可呼叫 `Item4QuizEngine.createAttempt(...)` 及 `Item4QuizEngine.gradeAttempt(...)`。瀏覽器端需取得題目資料；若將 `answer-key.json` 或完整 `attempt` 一併送到瀏覽器，使用者可從開發者工具讀取答案。正式考核應由伺服器建立作答版本、保留答案鍵，並在提交時於伺服器計分；瀏覽器只接收題目與選項。

## 轉移到其他平台

題庫使用一般 JSON 格式，方便轉換為平台 API、React/Vue 元件、資料庫記錄或 LMS 匯入格式。由於目標平台尚未指定，本套件不假設特定 LMS 或登入方式。若需要直接匯入 Moodle、Canvas、Google Forms 或其他平台，請提供平台名稱及其匯入格式／API 規格，再製作相應轉換器或套件。

## 領袖核實事項

題目按現行網站題庫整理，沒有在此重新核實歷史或人事資料。題庫中標示待核實的題目為：乙15、丙1至4、丙7、丙14、丙16及丙20。丙部20題含港島第82旅的專屬資料；若用於其他旅或地區，請先替換或移除該部分。答案鍵中的 `reviewNote` 保留了原有核實提示。
