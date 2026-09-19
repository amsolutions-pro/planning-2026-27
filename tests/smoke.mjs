/**
 * Épreuve de la page dans un vrai navigateur.
 *
 * Elle sert le dossier tel qu'il sera publié, ouvre `index.html` dans Chromium,
 * et vérifie ce qu'aucun test Python ne peut voir : que la page se dessine sans
 * erreur, que chaque onglet s'ouvre, que rien ne déborde sur un téléphone.
 *
 *   node tests/smoke.mjs            (NODE_PATH doit mener à playwright)
 *
 * La page n'a toujours aucune dépendance JavaScript : celle-ci est un outil
 * d'atelier, elle n'est jamais publiée.
 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  console.error('playwright introuvable. Installez-le puis relancez avec NODE_PATH pointant dessus.');
  process.exit(2);
}

// Chromium fourni par l'image, quand la version de playwright ne le trouve pas seule.
const CHROME = [process.env.CHROMIUM_EPREUVE, '/opt/pw-browsers/chromium'].find((c) => c && existsSync(c));
const RACINE = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.ico': 'image/x-icon', '.webmanifest': 'application/manifest+json',
  '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function servir() {
  const serveur = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    let rel = decodeURIComponent(url.pathname).replace(/^\/+/, '') || 'index.html';
    if (rel.endsWith('/')) rel += 'index.html';
    const fichier = path.join(RACINE, rel);
    if (!fichier.startsWith(RACINE) || !existsSync(fichier)) {
      res.writeHead(404, { 'content-type': 'text/plain' }); res.end('404'); return;
    }
    const corps = await readFile(fichier);
    res.writeHead(200, { 'content-type': TYPES[path.extname(fichier)] || 'application/octet-stream' });
    res.end(corps);
  });
  return new Promise((ok) => serveur.listen(0, '127.0.0.1', () => ok(serveur)));
}

const echecs = [];
const faits = [];
function verifier(nom, condition, detail) {
  if (condition) { faits.push(nom); return true; }
  echecs.push(detail ? `${nom} — ${detail}` : nom);
  return false;
}

const ONGLETS = ['semaine', 'actus', 'college', 'activites', 'garde', 'budget'];

async function main() {
  const serveur = await servir();
  const base = `http://127.0.0.1:${serveur.address().port}/`;
  const navigateur = await chromium.launch({ args: ['--no-sandbox'], ...(CHROME ? { executablePath: CHROME } : {}) });
  const erreurs = [];

  try {
    const contexte = await navigateur.newContext({
      viewport: { width: 1280, height: 900 },
      locale: 'fr-FR',
      timezoneId: 'Europe/Paris',
    });
    await contexte.route('**://fonts.{googleapis,gstatic}.com/**', (r) => r.abort());
    const page = await contexte.newPage();
    page.on('pageerror', (e) => erreurs.push('pageerror: ' + e.message));
    // « Failed to load resource » double ce que `requestfailed` dit déjà, en
    // moins précis : on ne garde que les vraies erreurs de script.
    page.on('console', (m) => {
      if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) erreurs.push('console: ' + m.text());
    });
    page.on('requestfailed', (r) => {
      // Les polices Google ne sortent pas de l'atelier : ce n'est pas un défaut de la page.
      if (!/fonts\.(googleapis|gstatic)\.com/.test(r.url())) {
        erreurs.push('requête échouée: ' + r.url());
      }
    });

    await page.goto(base + 'index.html', { waitUntil: 'load' });
    await page.waitForTimeout(400);

    verifier('titre', (await page.title()) === 'Planning Narek & Annie', await page.title());
    // Le samedi ne se montre que s'il porte quelque chose : la grille doit
    // afficher exactement les jours que la page dit afficher, ni plus ni moins.
    const joursDits = await page.evaluate(() => window.joursAffiches(window.perturbationsParJour()));
    const joursVus = await page.$$eval('#week-grid .day .day__name', (e) => e.map((x) => x.textContent.trim()));
    verifier('la semaine montre les jours attendus',
      JSON.stringify(joursDits) === JSON.stringify(joursVus),
      joursDits + ' ≠ ' + joursVus);
    verifier('le samedi vide reste hors de la semaine',
      joursVus.indexOf('Samedi') === -1 || joursDits.indexOf('Samedi') !== -1);

    for (const onglet of ONGLETS) {
      await page.click('#tab-' + onglet);
      await page.waitForTimeout(150);
      const visible = await page.locator('#panel-' + onglet).isVisible();
      verifier(`onglet ${onglet} s'ouvre`, visible);
      const choisi = await page.getAttribute('#tab-' + onglet, 'aria-selected');
      verifier(`onglet ${onglet} se dit choisi`, choisi === 'true', choisi);
    }

    await page.click('#tab-college');
    await page.waitForTimeout(200);
    verifier('la grille du collège a des cases',
      (await page.locator('#tt-grid td').count()) > 10,
      String(await page.locator('#tt-grid td').count()));

    await page.click('#tab-garde');
    await page.waitForTimeout(200);
    verifier('les semaines de garde sont listées',
      (await page.locator('#gd-months .gd-week').count()) > 20,
      String(await page.locator('#gd-months .gd-week').count()));
    verifier('les vacances sont listées',
      (await page.locator('#gd-vacances').innerText()).length > 40);

    await page.click('#tab-activites');
    await page.waitForTimeout(150);
    verifier('une carte d\'activités par enfant',
      (await page.locator('#act-grid > .card').count()) === 2,
      String(await page.locator('#act-grid > .card').count()));
    verifier('chaque inscription est listée',
      (await page.locator('#act-grid .act').count()) ===
        (await page.evaluate(() => window.INSCRIPTIONS.length)),
      String(await page.locator('#act-grid .act').count()));

    // --- Ce qui est daté s'efface tout seul ---
    const dates = await page.$$eval('[data-jusqu], [data-des]', (els) => {
      const jour = new Date();
      const ce_jour = Date.UTC(jour.getFullYear(), jour.getMonth(), jour.getDate());
      const ms = (c) => Date.UTC(+c.slice(0, 4), +c.slice(5, 7) - 1, +c.slice(8, 10));
      return els.map((el) => {
        const des = el.getAttribute('data-des'), jusqu = el.getAttribute('data-jusqu');
        const attendu = !!((des && ce_jour < ms(des)) || (jusqu && ce_jour > ms(jusqu)));
        return { quoi: (el.tagName + (el.className ? '.' + el.className : '')).toLowerCase(),
                 des, jusqu, attendu, cache: el.hidden };
      });
    });
    verifier('des blocs datés existent', dates.length > 0);
    const datesFausses = dates.filter((d) => d.attendu !== d.cache);
    verifier('chaque bloc daté est montré ou caché à l\'heure', datesFausses.length === 0,
      JSON.stringify(datesFausses));

    await page.click('#tab-semaine');
    await page.waitForTimeout(150);
    const reposDits = await page.locator('#week-grid .day--rest').count();
    const libreVisible = await page.locator('#stat-libre').isVisible();
    verifier('le compte des jours libres suit la grille',
      (reposDits > 0) === libreVisible, `${reposDits} jour(s) au repos, étiquette ${libreVisible}`);
    if (reposDits === 1) {
      const nom = (await page.locator('#week-grid .day--rest .day__name').innerText()).trim();
      verifier('le jour libre est nommé',
        (await page.locator('#stat-libre').innerText()).startsWith(nom),
        await page.locator('#stat-libre').innerText());
    }
    verifier('le compte des activités vient des inscriptions',
      (await page.locator('#stat-activites b').innerText()) ===
        String(await page.evaluate(() => window.INSCRIPTIONS.length)),
      await page.locator('#stat-activites').innerText());

    // Un créneau à venir s'annonce « Dès le … » ; une fois commencé, « Confirmé ».
    const badges = await page.evaluate(() => {
      const jour = new Date();
      const ce_jour = Date.UTC(jour.getFullYear(), jour.getMonth(), jour.getDate());
      const ms = (c) => Date.UTC(+c.slice(0, 4), +c.slice(5, 7) - 1, +c.slice(8, 10));
      return window.ACTIVITES.filter((a) => a.des)
        .map((a) => ({ id: a.id, avenir: ce_jour < ms(a.des), mot: window.badgeDe(a) }));
    });
    verifier('des créneaux portent une date d\'entrée en vigueur', badges.length > 0);
    const badgesFaux = badges.filter((b) => b.avenir !== /^Dès le /.test(b.mot));
    verifier('« Dès le … » ne reste pas après coup', badgesFaux.length === 0, JSON.stringify(badgesFaux));

    // --- Le budget doit tomber juste ---
    await page.click('#tab-budget');
    await page.waitForTimeout(150);
    const euros = (t) => Number(String(t).replace(/[^0-9]/g, '')) || 0;
    const postes = await page.$$eval('#panel-budget .money--n li, #panel-budget .money--a li',
      (els) => els.map((el) => el.querySelector('b').textContent));
    const sommes = await page.$$eval('#panel-budget .money__sum', (els) => els.map((el) => el.textContent));
    const total = euros(await page.locator('.budget-top__fig strong').innerText());
    verifier('le total du budget est la somme des postes',
      postes.reduce((a, b) => a + euros(b), 0) === total,
      postes.join(' + ') + ' ≠ ' + total);
    verifier('les sommes par enfant font le total',
      sommes.reduce((a, b) => a + euros(b), 0) === total,
      sommes.join(' + ') + ' ≠ ' + total);
    const parts = await page.$$eval('#panel-budget .bar__top b', (els) => els.map((el) => el.textContent));
    verifier('la répartition couvre le total',
      parts.reduce((a, b) => a + euros(b.split('·')[0]), 0) === total,
      parts.join(' / '));
    const pourcents = parts.map((t) => Number(t.split('·')[1].replace(/[^0-9]/g, '')));
    verifier('la répartition fait 100 %', pourcents.reduce((a, b) => a + b, 0) === 100,
      pourcents.join(' + '));
    const largeurs = await page.$$eval('#panel-budget .bar__fill', (els) => els.map((el) => el.style.width));
    verifier('les barres montrent leur part',
      JSON.stringify(largeurs) === JSON.stringify(pourcents.map((n) => n + '%')),
      largeurs.join(' / '));
    verifier('le nombre d\'activités annoncé est le bon',
      (await page.locator('.budget-top__fig p').innerText())
        .startsWith(String(await page.evaluate(() => window.INSCRIPTIONS.length)) + ' activités'),
      await page.locator('.budget-top__fig p').innerText());

    // --- Journées superposées : autant de colonnes que de jours ---
    await page.click('#tab-college');
    await page.click('#vue-super');
    await page.waitForTimeout(250);
    const colonnes = await page.evaluate(() => {
      const el = document.querySelector('.ovv');
      if (!el) return null;
      return { dit: el.style.getPropertyValue('--cols'),
               titres: document.querySelectorAll('.ovv__title').length };
    });
    verifier('les journées superposées ont leurs colonnes',
      colonnes && String(colonnes.titres) === String(colonnes.dit),
      JSON.stringify(colonnes));
    await page.click('#vue-grille');

    // --- Accessibilité de base : tout ce qui se clique doit se nommer ---
    const muets = await page.$$eval('button, a[href], input, select', (els) => els
      .filter((el) => {
        if (el.closest('[hidden]')) return false;
        const nom = (el.getAttribute('aria-label') || el.innerText || el.value ||
          (el.labels && el.labels[0] && el.labels[0].innerText) || '').trim();
        return !nom;
      })
      .map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + '.' + el.className));
    verifier('tout ce qui se clique porte un nom', muets.length === 0, muets.join(', '));

    const doublons = await page.evaluate(() => {
      const vus = {}, doubles = [];
      document.querySelectorAll('[id]').forEach((el) => {
        if (vus[el.id]) doubles.push(el.id); else vus[el.id] = 1;
      });
      return doubles;
    });
    verifier('aucun identifiant en double', doublons.length === 0, doublons.join(', '));

    // --- Téléphone : rien ne doit déborder sur le côté ---
    const tel = await contexte.newPage();
    tel.on('pageerror', (e) => erreurs.push('pageerror (tél.): ' + e.message));
    await tel.setViewportSize({ width: 390, height: 844 });
    await tel.goto(base + 'index.html', { waitUntil: 'load' });
    await tel.waitForTimeout(400);
    for (const onglet of ONGLETS) {
      await tel.click('#tab-' + onglet);
      await tel.waitForTimeout(200);
      const trop = await tel.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      verifier(`téléphone · ${onglet} ne déborde pas`, trop <= 1, trop + 'px');
    }
    await tel.close();

    verifier('aucune erreur de script', erreurs.length === 0, erreurs.slice(0, 6).join(' | '));
  } finally {
    await navigateur.close();
    serveur.close();
  }

  console.log(`${faits.length} vérification(s) passée(s)`);
  if (echecs.length) {
    console.error('\nÉCHECS :');
    echecs.forEach((e) => console.error('  · ' + e));
    process.exit(1);
  }
  console.log('OK');
}

main().catch((e) => { console.error(e); process.exit(1); });
