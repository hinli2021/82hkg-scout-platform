"use strict";

const assert = require("node:assert/strict");
const bank = require("./question-bank.json");
const key = require("./answer-key.json");
const engine = require("./quiz-engine.js");

const attempt = engine.createAttempt(bank, key, { shuffleOptions: true });
assert.equal(attempt.quiz.questions.length, 50);
assert.equal(attempt.quiz.scoring.maxScore, 100);
assert.equal(attempt.quiz.scoring.passScore, 80);
assert.equal(attempt.quiz.questions.filter(q => q.partId === "world").length, 15);
assert.equal(attempt.quiz.questions.filter(q => q.partId === "hk").length, 15);
assert.equal(attempt.quiz.questions.filter(q => q.partId === "group").length, 20);
assert.ok(attempt.quiz.questions.every(q => q.options.length === 4));
assert.ok(attempt.quiz.questions.every(q => !Object.hasOwn(q, "answerIndex")));

const allCorrect = Object.fromEntries(attempt.quiz.questions.map(q => [q.id, attempt.answerKey[q.id].correctOptionIndex]));
const perfect = engine.gradeAttempt(attempt, allCorrect);
assert.equal(perfect.score, 100);
assert.equal(perfect.passed, true);
assert.equal(perfect.answeredCount, 50);

const exactlyPass = Object.fromEntries(attempt.quiz.questions.map((q, i) => [
  q.id,
  i < 40 ? attempt.answerKey[q.id].correctOptionIndex : (attempt.answerKey[q.id].correctOptionIndex + 1) % q.options.length
]));
const passResult = engine.gradeAttempt(attempt, exactlyPass);
assert.equal(passResult.score, 80);
assert.equal(passResult.passed, true);

const belowPass = Object.fromEntries(attempt.quiz.questions.map((q, i) => [
  q.id,
  i < 39 ? attempt.answerKey[q.id].correctOptionIndex : (attempt.answerKey[q.id].correctOptionIndex + 1) % q.options.length
]));
const failResult = engine.gradeAttempt(attempt, belowPass);
assert.equal(failResult.score, 78);
assert.equal(failResult.passed, false);

const twoParts = engine.createAttempt(bank, key, { parts: ["world", "hk"], shuffleOptions: false });
assert.equal(twoParts.quiz.questions.length, 30);
assert.equal(twoParts.quiz.scoring.maxScore, 60);
assert.equal(twoParts.quiz.scoring.passScore, 48);

console.log("All quiz-package tests passed: 50 items, 15/15/20 section counts, shuffled choices, private answer-key separation, score and 80% pass threshold.");
