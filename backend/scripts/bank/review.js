const fs = require('fs');
const path = require('path');

const aigenDir = path.join(__dirname, 'aigen');
const outFile = path.join(__dirname, 'review.html');

const files = fs.readdirSync(aigenDir).filter(f => f.endsWith('.json')).sort();

const allData = files.map(file => {
  const raw = JSON.parse(fs.readFileSync(path.join(aigenDir, file), 'utf8'));
  return { file, theme: raw.theme, difficulty: raw.difficulty, questions: raw.questions };
});

const themes = [...new Set(allData.map(d => d.theme))].sort();
const difficulties = [...new Set(allData.map(d => d.difficulty))].sort();

const totalQuestions = allData.reduce((s, d) => s + d.questions.length, 0);

function escape(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderQuestion(q, idx, file, theme, difficulty) {
  const choices = q.choices.map(c => {
    const isAnswer = c === q.answer;
    return `<li class="${isAnswer ? 'correct' : ''}">${isAnswer ? '●' : '○'} ${escape(c)}</li>`;
  }).join('\n');

  return `
<div class="card" data-theme="${escape(theme)}" data-difficulty="${escape(difficulty)}">
  <div class="card-meta">
    <span class="badge theme">${escape(theme)}</span>
    <span class="badge diff">${escape(difficulty)}</span>
    <span class="file-label">${escape(file)} · Q${idx + 1}</span>
  </div>
  <p class="question">${escape(q.question)}</p>
  <ul class="choices">${choices}</ul>
  ${q.anecdote ? `<p class="anecdote">💡 ${escape(q.anecdote)}</p>` : ''}
</div>`;
}

const cardsHtml = allData.map(({ file, theme, difficulty, questions }) =>
  questions.map((q, i) => renderQuestion(q, i, file, theme, difficulty)).join('\n')
).join('\n');

const themeButtons = ['all', ...themes].map(t =>
  `<button class="filter-btn${t === 'all' ? ' active' : ''}" data-theme="${t}">${t === 'all' ? 'Tout' : t}</button>`
).join('\n');

const diffButtons = ['all', ...difficulties].map(d =>
  `<button class="filter-btn diff-btn${d === 'all' ? ' active' : ''}" data-diff="${d}">${d === 'all' ? 'Tout' : d}</button>`
).join('\n');

const html = `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review — ${totalQuestions} questions</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; padding: 24px; }
  h1 { font-size: 1.4rem; margin-bottom: 8px; }
  .subtitle { color: #666; font-size: 0.9rem; margin-bottom: 20px; }
  .filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; align-items: center; }
  .filters label { font-size: 0.8rem; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-right: 4px; }
  .filter-btn {
    padding: 5px 12px; border: 1px solid #ccc; border-radius: 20px;
    background: #fff; cursor: pointer; font-size: 0.85rem; transition: all .15s;
  }
  .filter-btn:hover { border-color: #555; }
  .filter-btn.active { background: #222; color: #fff; border-color: #222; }
  .diff-btn.active { background: #1a6b3a; border-color: #1a6b3a; color: #fff; }
  .counter { font-size: 0.85rem; color: #666; margin: 12px 0 16px; }

  .card {
    background: #fff; border-radius: 10px; padding: 18px 20px;
    margin-bottom: 14px; border: 1px solid #e0e0e0;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }
  .card.hidden { display: none; }
  .card-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .badge {
    font-size: 0.72rem; font-weight: 700; padding: 2px 9px; border-radius: 12px;
    text-transform: uppercase; letter-spacing: .04em;
  }
  .badge.theme { background: #e8f0fe; color: #1a56c4; }
  .badge.diff { background: #e8f5e9; color: #2e7d32; }
  .file-label { font-size: 0.78rem; color: #999; margin-left: auto; }
  .question { font-size: 1rem; font-weight: 600; line-height: 1.5; margin-bottom: 12px; }
  .choices { list-style: none; display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
  .choices li { font-size: 0.9rem; padding: 5px 10px; border-radius: 6px; background: #fafafa; border: 1px solid #eee; }
  .choices li.correct { background: #e8f5e9; border-color: #81c784; color: #1b5e20; font-weight: 700; }
  .anecdote { font-size: 0.83rem; color: #555; background: #fffde7; border-left: 3px solid #f9a825; padding: 8px 12px; border-radius: 4px; line-height: 1.5; }
</style>
</head>
<body>
<h1>Review des questions</h1>
<p class="subtitle">Générée le ${new Date().toLocaleDateString('fr-FR')} · ${totalQuestions} questions · ${files.length} fichiers</p>

<div class="filters">
  <label>Thème :</label>
  ${themeButtons}
</div>
<div class="filters">
  <label>Difficulté :</label>
  ${diffButtons}
</div>
<p class="counter" id="counter"></p>

<div id="cards">
${cardsHtml}
</div>

<script>
  let activeTheme = 'all';
  let activeDiff = 'all';

  function applyFilters() {
    const cards = document.querySelectorAll('.card');
    let visible = 0;
    cards.forEach(card => {
      const themeOk = activeTheme === 'all' || card.dataset.theme === activeTheme;
      const diffOk = activeDiff === 'all' || card.dataset.difficulty === activeDiff;
      const show = themeOk && diffOk;
      card.classList.toggle('hidden', !show);
      if (show) visible++;
    });
    document.getElementById('counter').textContent = visible + ' question' + (visible !== 1 ? 's' : '') + ' affichée' + (visible !== 1 ? 's' : '');
  }

  document.querySelectorAll('.filter-btn[data-theme]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn[data-theme]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeTheme = btn.dataset.theme;
      applyFilters();
    });
  });

  document.querySelectorAll('.filter-btn[data-diff]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn[data-diff]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeDiff = btn.dataset.diff;
      applyFilters();
    });
  });

  applyFilters();
</script>
</body>
</html>`;

fs.writeFileSync(outFile, html, 'utf8');
console.log(`✓ ${totalQuestions} questions écrites dans : ${outFile}`);
