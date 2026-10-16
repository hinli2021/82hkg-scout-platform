/*
 * 第4項童軍會員章測驗引擎
 * 無第三方依賴；支援瀏覽器全域變數及 Node.js CommonJS。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.Item4QuizEngine = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function assert(condition, message) {
    if (!condition) throw new Error(message);
  }

  function shuffleCopy(items, rng) {
    const result = items.slice();
    const random = typeof rng === "function" ? rng : Math.random;
    for (let i = result.length - 1; i > 0; i -= 1) {
      const raw = Number(random());
      const safe = Number.isFinite(raw) ? Math.max(0, Math.min(0.999999999, raw)) : Math.random();
      const j = Math.floor(safe * (i + 1));
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
  }

  function validateBank(bank, answerKey) {
    assert(bank && typeof bank === "object", "題庫資料格式無效。");
    assert(Array.isArray(bank.questions) && bank.questions.length > 0, "題庫沒有題目。");
    assert(answerKey && typeof answerKey === "object" && Array.isArray(answerKey.answers), "答案資料格式無效。");
    assert(bank.quizId === answerKey.quizId, "題庫與答案鍵的 quizId 不相符。");

    const questionIds = new Set();
    for (const q of bank.questions) {
      assert(q && typeof q.id === "string" && q.id.length > 0, "每道題目均須有 id。");
      assert(!questionIds.has(q.id), `題目 id 重複：${q.id}`);
      questionIds.add(q.id);
      assert(typeof q.prompt === "string" && q.prompt.length > 0, `題目文字缺失：${q.id}`);
      assert(Array.isArray(q.options) && q.options.length >= 2, `選項數目不足：${q.id}`);
      assert(q.options.every(option => typeof option === "string"), `選項必須為文字：${q.id}`);
    }

    const keyById = new Map();
    for (const a of answerKey.answers) {
      assert(a && typeof a.id === "string", "答案鍵項目缺少 id。");
      assert(!keyById.has(a.id), `答案鍵 id 重複：${a.id}`);
      keyById.set(a.id, a);
    }
    for (const q of bank.questions) {
      const a = keyById.get(q.id);
      assert(a, `答案鍵缺少題目：${q.id}`);
      assert(Number.isInteger(a.answerIndex) && a.answerIndex >= 0 && a.answerIndex < q.options.length,
        `答案索引無效：${q.id}`);
    }
    return keyById;
  }

  /**
   * 建立一次作答。題目順序預設按題庫排列；選項預設隨機排列。
   * 傳回的 answerKey 必須留在伺服器端，切勿將它送到作答者的瀏覽器。
   */
  function createAttempt(questionBank, answerKey, settings) {
    const config = settings || {};
    const keyById = validateBank(questionBank, answerKey);
    const allowedParts = Array.isArray(config.parts) ? new Set(config.parts) : null;
    let sourceQuestions = questionBank.questions.filter(q => !allowedParts || allowedParts.has(q.partId));

    if (Array.isArray(config.questionIds)) {
      const chosen = new Set(config.questionIds);
      sourceQuestions = sourceQuestions.filter(q => chosen.has(q.id));
      assert(sourceQuestions.length === chosen.size, "指定題目中有不存在或不屬於所選部分的 id。");
    }

    const shuffleQuestions = config.shuffleQuestions == null
      ? !!(questionBank.defaults && questionBank.defaults.shuffleQuestions)
      : !!config.shuffleQuestions;
    const shuffleOptions = config.shuffleOptions == null
      ? !(questionBank.defaults && questionBank.defaults.shuffleOptions === false)
      : !!config.shuffleOptions;
    const rng = typeof config.rng === "function" ? config.rng : Math.random;
    if (shuffleQuestions) sourceQuestions = shuffleCopy(sourceQuestions, rng);

    const requestedCount = config.questionCount == null ? sourceQuestions.length : Number(config.questionCount);
    assert(Number.isInteger(requestedCount) && requestedCount > 0, "questionCount 必須是正整數。");
    assert(requestedCount <= sourceQuestions.length, "questionCount 大於可用題數。");
    sourceQuestions = sourceQuestions.slice(0, requestedCount);

    const pointsPerQuestion = Number(config.pointsPerQuestion == null
      ? questionBank.scoring.pointsPerQuestion
      : config.pointsPerQuestion);
    const passPercent = Number(config.passPercent == null
      ? questionBank.scoring.passPercent
      : config.passPercent);
    assert(Number.isFinite(pointsPerQuestion) && pointsPerQuestion > 0, "每題分數設定無效。");
    assert(Number.isFinite(passPercent) && passPercent >= 0 && passPercent <= 100, "合格百分比設定無效。");

    const maxScore = sourceQuestions.length * pointsPerQuestion;
    const passScore = config.passScore == null
      ? Math.ceil(maxScore * passPercent / 100)
      : Number(config.passScore);
    assert(Number.isFinite(passScore) && passScore >= 0 && passScore <= maxScore,
      "合格分數必須介乎 0 與滿分之間。");

    const privateKey = Object.create(null);
    const visibleQuestions = sourceQuestions.map(q => {
      const optionOrder = shuffleOptions
        ? shuffleCopy(q.options.map((_, index) => index), rng)
        : q.options.map((_, index) => index);
      const displayedOptions = optionOrder.map(index => q.options[index]);
      const sourceAnswer = keyById.get(q.id);
      const correctOptionIndex = optionOrder.indexOf(sourceAnswer.answerIndex);
      privateKey[q.id] = {
        correctOptionIndex,
        correctOptionText: displayedOptions[correctOptionIndex],
        explanation: sourceAnswer.explanation || "",
        reviewNote: sourceAnswer.reviewNote || null
      };
      return {
        id: q.id,
        order: q.order,
        partId: q.partId,
        partTitle: q.partTitle,
        prompt: q.prompt,
        options: displayedOptions,
        showColorSwatch: !!q.showColorSwatch
      };
    });

    const parts = (questionBank.parts || []).filter(part => visibleQuestions.some(q => q.partId === part.id));
    const quiz = {
      quizId: questionBank.quizId,
      title: questionBank.title,
      language: questionBank.language,
      questions: visibleQuestions,
      parts,
      scoring: {
        pointsPerQuestion,
        questionCount: visibleQuestions.length,
        maxScore,
        passScore,
        passPercent: maxScore ? Math.round(passScore / maxScore * 10000) / 100 : 0
      }
    };

    return { quiz, answerKey: privateKey };
  }

  function getResponse(responses, question, index) {
    let value;
    if (Array.isArray(responses)) value = responses[index];
    else if (responses && typeof responses === "object") value = responses[question.id];
    if (value && typeof value === "object") {
      value = value.selectedIndex == null ? value.choiceIndex : value.selectedIndex;
    }
    if (value == null || value === "") return null;
    const selected = Number(value);
    return Number.isInteger(selected) && selected >= 0 && selected < question.options.length ? selected : null;
  }

  /** responses 可用與題目順序對應的陣列，或以題目 id 為鍵的物件。 */
  function gradeAttempt(attempt, responses) {
    assert(attempt && attempt.quiz && Array.isArray(attempt.quiz.questions), "作答資料格式無效。");
    assert(attempt.answerKey && typeof attempt.answerKey === "object", "缺少作答答案鍵。");
    const quiz = attempt.quiz;
    const scoring = quiz.scoring;
    const sections = Object.create(null);
    for (const part of quiz.parts || []) {
      sections[part.id] = {
        partId: part.id,
        partTitle: part.title,
        questionCount: 0,
        correctCount: 0,
        score: 0,
        maxScore: 0
      };
    }

    let correctCount = 0;
    let answeredCount = 0;
    const review = quiz.questions.map((q, index) => {
      const key = attempt.answerKey[q.id];
      assert(key && Number.isInteger(key.correctOptionIndex), `作答答案鍵缺少題目：${q.id}`);
      const selectedIndex = getResponse(responses, q, index);
      const answered = selectedIndex !== null;
      const correct = answered && selectedIndex === key.correctOptionIndex;
      const section = sections[q.partId] || (sections[q.partId] = {
        partId: q.partId, partTitle: q.partTitle, questionCount: 0, correctCount: 0, score: 0, maxScore: 0
      });
      section.questionCount += 1;
      section.maxScore += scoring.pointsPerQuestion;
      if (answered) answeredCount += 1;
      if (correct) {
        correctCount += 1;
        section.correctCount += 1;
        section.score += scoring.pointsPerQuestion;
      }
      return {
        id: q.id,
        partId: q.partId,
        partTitle: q.partTitle,
        prompt: q.prompt,
        selectedIndex,
        selectedOption: answered ? q.options[selectedIndex] : null,
        correctOptionIndex: key.correctOptionIndex,
        correctOption: key.correctOptionText || q.options[key.correctOptionIndex],
        correct,
        unanswered: !answered,
        explanation: key.explanation || "",
        reviewNote: key.reviewNote || null
      };
    });

    const score = correctCount * scoring.pointsPerQuestion;
    return {
      quizId: quiz.quizId,
      title: quiz.title,
      score,
      maxScore: scoring.maxScore,
      passScore: scoring.passScore,
      correctCount,
      questionCount: quiz.questions.length,
      answeredCount,
      unansweredCount: quiz.questions.length - answeredCount,
      passed: score >= scoring.passScore,
      sections: Object.values(sections),
      review
    };
  }

  return { shuffleCopy, validateBank, createAttempt, gradeAttempt };
});
