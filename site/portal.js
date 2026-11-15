/* Bom Dia Petrópolis: relógio, carrossel, tempo e busca.
   Tudo roda no navegador do leitor; se um serviço externo falhar, o quadro some sem quebrar a página. */
(function () {
  'use strict';
  var base = document.body.dataset.base || '';
  var reduzirMovimento = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Relógio (horário de Brasília) */
  var relogio = document.querySelector('[data-relogio]');
  if (relogio) {
    var fmt = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'America/Sao_Paulo' });
    var tic = function () { relogio.textContent = fmt.format(new Date()); };
    tic(); setInterval(tic, 1000);
  }

  /* Carrossel da capa */
  document.querySelectorAll('.carrossel').forEach(function (c) {
    var trilho = c.querySelector('.carrossel-trilho');
    var slides = c.querySelectorAll('.slide');
    var pontos = c.querySelectorAll('.pontos button');
    if (slides.length < 2) return;
    var atual = 0, timer = null;
    var ir = function (i) {
      atual = (i + slides.length) % slides.length;
      trilho.scrollTo({ left: slides[atual].offsetLeft - trilho.offsetLeft, behavior: reduzirMovimento ? 'auto' : 'smooth' });
    };
    var marcar = function () {
      var i = Math.round(trilho.scrollLeft / trilho.clientWidth);
      atual = i;
      pontos.forEach(function (p, j) { if (j === i) p.setAttribute('aria-current', 'true'); else p.removeAttribute('aria-current'); });
    };
    trilho.addEventListener('scroll', function () { clearTimeout(trilho._t); trilho._t = setTimeout(marcar, 80); });
    pontos.forEach(function (p, j) { p.addEventListener('click', function () { ir(j); reiniciar(); }); });
    c.querySelector('[data-anterior]').addEventListener('click', function () { ir(atual - 1); reiniciar(); });
    c.querySelector('[data-proximo]').addEventListener('click', function () { ir(atual + 1); reiniciar(); });
    var reiniciar = function () {
      clearInterval(timer);
      if (!reduzirMovimento) timer = setInterval(function () { ir(atual + 1); }, 7000);
    };
    c.addEventListener('mouseenter', function () { clearInterval(timer); });
    c.addEventListener('mouseleave', reiniciar);
    c.addEventListener('focusin', function () { clearInterval(timer); });
    reiniciar();
  });

  /* Tempo em Petrópolis (Open-Meteo, gratuito e sem chave) */
  var CODIGOS = [
    [[0], '☀️', 'Céu limpo'], [[1], '🌤️', 'Poucas nuvens'], [[2], '⛅', 'Parcialmente nublado'],
    [[3], '☁️', 'Nublado'], [[45, 48], '🌫️', 'Neblina'], [[51, 53, 55, 56, 57], '🌦️', 'Garoa'],
    [[61, 63, 65, 66, 67, 80, 81, 82], '🌧️', 'Chuva'], [[71, 73, 75, 77, 85, 86], '🌨️', 'Frio intenso'],
    [[95, 96, 99], '⛈️', 'Trovoadas']
  ];
  var clima = function (cod) {
    for (var i = 0; i < CODIGOS.length; i++) if (CODIGOS[i][0].indexOf(cod) >= 0) return CODIGOS[i];
    return [[], '🌡️', ''];
  };
  var caixaTempo = document.querySelectorAll('[data-tempo]');
  if (caixaTempo.length) {
    fetch('https://api.open-meteo.com/v1/forecast?latitude=-22.505&longitude=-43.178' +
      '&current=temperature_2m,weather_code,relative_humidity_2m' +
      '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max' +
      '&timezone=America%2FSao_Paulo&forecast_days=4')
      .then(function (r) { if (!r.ok) throw r; return r.json(); })
      .then(function (d) {
        var c = clima(d.current.weather_code);
        var dias = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
        var prox = '';
        for (var i = 1; i < d.daily.time.length; i++) {
          var dia = new Date(d.daily.time[i] + 'T12:00:00');
          prox += '<li><span>' + dias[dia.getDay()] + '</span><b>' + clima(d.daily.weather_code[i])[1] + '</b>' +
            Math.round(d.daily.temperature_2m_max[i]) + '° <small>' + Math.round(d.daily.temperature_2m_min[i]) + '°</small></li>';
        }
        var html = '<div class="tempo-agora"><span class="tempo-icone">' + c[1] + '</span>' +
          '<strong>' + Math.round(d.current.temperature_2m) + '°</strong>' +
          '<div><b>' + c[2] + '</b><span>Mín. ' + Math.round(d.daily.temperature_2m_min[0]) + '° · Máx. ' +
          Math.round(d.daily.temperature_2m_max[0]) + '°<br>Chance de chuva ' + (d.daily.precipitation_probability_max[0] || 0) + '%</span></div></div>' +
          '<ul class="tempo-dias">' + prox + '</ul>';
        caixaTempo.forEach(function (el) { el.innerHTML = html; });
      })
      .catch(function () { caixaTempo.forEach(function (el) { el.closest('.caixa').hidden = true; }); });
  }

  /* Busca */
  var resultados = document.querySelector('[data-busca-resultados]');
  if (resultados) {
    var q = (new URLSearchParams(location.search).get('q') || '').trim();
    var status = document.querySelector('[data-busca-status]');
    document.querySelectorAll('.busca input').forEach(function (i) { i.value = q; });
    if (!q) { status.textContent = 'Digite o que você procura.'; return; }
    var sem = function (t) { return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); };
    var esc = function (t) { var d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
    var termos = sem(q).split(/\s+/);
    fetch(base + 'busca.json').then(function (r) { return r.json(); }).then(function (lista) {
      var achados = lista.filter(function (m) {
        var texto = sem(m.t + ' ' + m.r + ' ' + m.s + ' ' + m.k);
        return termos.every(function (t) { return texto.indexOf(t) >= 0; });
      });
      status.textContent = achados.length
        ? achados.length + (achados.length === 1 ? ' matéria encontrada' : ' matérias encontradas') + ' para “' + q + '”.'
        : 'Nada encontrado para “' + q + '”. Tente outra palavra.';
      resultados.innerHTML = achados.map(function (m) {
        return '<article class="cartao deitado sem-foto"><div class="cartao-texto">' +
          '<a class="chapeu ' + sem(m.s) + '" href="' + base + sem(m.s) + '.html">' + esc(m.s) + '</a>' +
          '<h3><a href="' + base + m.u + '">' + esc(m.t) + '</a></h3><p>' + esc(m.r) + '</p>' +
          '<span class="quando">' + esc(m.d) + '</span></div></article>';
      }).join('');
    });
  }
})();
