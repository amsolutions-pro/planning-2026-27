/**
 * Épreuve de la page avec des données PRONOTE.
 *
 * Le fichier des actualités est chiffré en production : aucune épreuve ne peut
 * le lire. Celle-ci en fabrique un faux, en clair — le format le permet — et le
 * sert à la place, pour éprouver tout ce qui ne se voit qu'avec des données :
 * la grille qui vient de PRONOTE, les marques posées sur les cases, le bloc
 * « Aujourd'hui », et le fait que du texte venu du collège ne peut pas devenir
 * du HTML.
 *
 *   node tests/pronote.mjs        (NODE_PATH doit mener à playwright)
 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); }
catch (e) { console.error('playwright introuvable.'); process.exit(2); }

const CHROME = [process.env.CHROMIUM_EPREUVE, '/opt/pw-browsers/chromium'].find((c) => c && existsSync(c));
const RACINE = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MS_JOUR = 86400000;

// Le poison : du HTML dans un champ que le collège remplit librement. S'il
// arrive jusqu'au DOM comme balise, la phrase de passe et le jeton de la page
// sont lisibles par qui l'a écrit.
const POISON = '<img src=x onerror="window.__perce=1">B12';

function lundiCourant() {
  const d = new Date();
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));
}
const cle = (ms) => new Date(ms).toISOString().slice(0, 10);

function fabriquerFichier() {
  const lundi = lundiCourant();
  const jour = (i) => cle(lundi + i * MS_JOUR);
  // Quatre jours garnis : au-dessus du garde-fou des trois jours, donc la page
  // doit préférer cette grille-là au décalque de septembre.
  const seances = [
    { date: jour(0), debut: '08:10', fin: '09:05', matiere: 'Mathématiques', prof: 'Mme A', salle: 'A01', statut: '', controle: false },
    { date: jour(0), debut: '16:50', fin: '17:45', matiere: 'Anglais', prof: 'M. B', salle: POISON, statut: '', controle: false },
    { date: jour(1), debut: '10:20', fin: '11:15', matiere: 'Français', prof: 'Mme C', salle: 'C03', statut: '', controle: false },
    { date: jour(2), debut: '08:10', fin: '09:05', matiere: 'SVT', prof: 'M. D', salle: 'D04', statut: '', controle: false },
    // Jeudi : un contrôle annoncé ET la séance annulée, au même créneau. C'est
    // le cas qui rendait la grille muette sur l'un des deux.
    { date: jour(3), debut: '13:45', fin: '14:40', matiere: 'Histoire-géo', prof: 'M. E', salle: 'E05', statut: 'Cours annulé', controle: true },
    // Et la dernière heure du jeudi saute aussi : la sortie doit avancer.
    { date: jour(3), debut: '15:55', fin: '16:50', matiere: 'Technologie', prof: 'M. F', salle: 'F06', statut: '', controle: false },
    { date: jour(3), debut: '16:50', fin: '17:45', matiere: 'Musique', prof: 'M. G', salle: 'G07', statut: 'Cours annulé', controle: false },
  ];
  const actualites = [
    { type: 'cours', niveau: 'important', raison: 'Cours annulé', titre: 'Cours annulé — Histoire-géo',
      detail: 'M. E · E05', matiere: 'Histoire-géo', date: jour(3), heure: '13:45',
      horizon: 'avenir', id: 'cours~aaaa000000000001', enfants: ['narek'], signale_le: new Date().toISOString() },
    { type: 'controle', niveau: 'scolaire', titre: 'Contrôle — Histoire-géo',
      detail: 'Évaluation nationale', matiere: 'Histoire-géo', date: jour(3), heure: '13:45',
      horizon: 'avenir', id: 'controle~aaaa000000000002', enfants: ['narek'], signale_le: new Date().toISOString() },
    { type: 'cours', niveau: 'important', raison: 'Cours annulé', titre: 'Cours annulé — Musique',
      detail: 'M. G · G07', matiere: 'Musique', date: jour(3), heure: '16:50',
      horizon: 'avenir', id: 'cours~aaaa000000000003', enfants: ['narek'], signale_le: new Date().toISOString() },
  ];
  // Le robot publie trois semaines : la semaine qui vient doit l'être aussi,
  // sans quoi le bloc « Aujourd'hui » d'un samedi retombe sur le décalque.
  const suivante = seances.map((c) => Object.assign({}, c, { date: cle(Date.parse(c.date) + 7 * MS_JOUR) }));
  seances.push.apply(seances, suivante);
  // Une matière qui n'existe que la semaine prochaine : elle prouve que la
  // navigation va bien chercher les séances de cette semaine-là.
  seances.push({ date: jour(9), debut: '09:05', fin: '10:00', matiere: 'Latin la semaine prochaine',
                 prof: 'Mme H', salle: 'H08', statut: '', controle: false });

  return {
    version: 1, empreinte: 'epreuve', mis_a_jour_le: new Date().toISOString(), chiffre: false,
    donnees: {
      version: 1, mis_a_jour_le: new Date().toISOString(), etablissement: 'Collège d’épreuve',
      depot: null, regles: { important: ['épreuve'], scolaire: ['épreuve'] },
      enfants: [
        { id: 'narek', nom: 'Narek', classe: '5F', seances: seances },
        { id: 'annie', nom: 'Annie', classe: '3F', seances: [] },
      ],
      actualites: actualites, erreurs: [],
    },
  };
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.ico': 'image/x-icon', '.webmanifest': 'application/manifest+json' };

function servir() {
  const serveur = createServer(async (req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
    const fichier = path.join(RACINE, rel);
    if (!fichier.startsWith(RACINE) || !existsSync(fichier)) { res.writeHead(404).end('404'); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(fichier)] || 'application/octet-stream' });
    res.end(await readFile(fichier));
  });
  return new Promise((ok) => serveur.listen(0, '127.0.0.1', () => ok(serveur)));
}

const echecs = [], faits = [];
function verifier(nom, condition, detail) {
  if (condition) { faits.push(nom); return true; }
  echecs.push(detail ? `${nom} — ${detail}` : nom);
  return false;
}

async function main() {
  const serveur = await servir();
  const base = `http://127.0.0.1:${serveur.address().port}/`;
  const navigateur = await chromium.launch({ args: ['--no-sandbox'], ...(CHROME ? { executablePath: CHROME } : {}) });
  const erreurs = [];
  try {
    const contexte = await navigateur.newContext({ viewport: { width: 1280, height: 950 }, locale: 'fr-FR', timezoneId: 'Europe/Paris' });
    await contexte.route('**://fonts.{googleapis,gstatic}.com/**', (r) => r.abort());
    await contexte.route('**/pronote/actualites.json*', (r) =>
      r.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(fabriquerFichier()) }));

    const page = await contexte.newPage();
    page.on('pageerror', (e) => erreurs.push('pageerror: ' + e.message));
    page.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) erreurs.push('console: ' + m.text()); });
    await page.goto(base + 'index.html', { waitUntil: 'load' });
    await page.waitForTimeout(700);

    // --- La grille vient bien de PRONOTE ---
    await page.click('#tab-college');
    await page.waitForTimeout(300);
    verifier('la grille se dit « d’après PRONOTE »',
      (await page.locator('#tt-regime').innerText()).includes('PRONOTE'),
      await page.locator('#tt-regime').innerText());

    // --- Le texte du collège ne devient jamais du HTML ---
    verifier('aucune balise injectée depuis PRONOTE',
      (await page.evaluate(() => window.__perce)) === undefined &&
      (await page.locator('#tt-grid img').count()) === 0,
      'window.__perce=' + (await page.evaluate(() => window.__perce)));
    verifier('la salle piégée s’affiche comme du texte',
      (await page.locator('#tt-grid').innerText()).includes('onerror'),
      'texte absent de la grille');

    // --- Contrôle et annulation au même créneau : les deux se lisent ---
    const caseJeudi = page.locator('#tt-grid .lesson', { hasText: 'Histoire-géo' }).first();
    const texteCase = await caseJeudi.innerText();
    verifier('le contrôle est annoncé sur la case', /Contrôle/.test(texteCase), texteCase.replace(/\n/g, ' | '));
    verifier('l’annulation est annoncée sur la même case', /annul/i.test(texteCase), texteCase.replace(/\n/g, ' | '));
    verifier('la page dit que les deux ne se résolvent pas',
      /à vérifier/i.test(texteCase), texteCase.replace(/\n/g, ' | '));
    verifier('la matière est barrée quand la séance saute',
      (await caseJeudi.getAttribute('class')).includes('lesson--annule'),
      await caseJeudi.getAttribute('class'));

    // --- Journées superposées : la sortie tient compte de l'annulation ---
    await page.click('#vue-super');
    await page.waitForTimeout(300);
    verifier('les journées superposées annoncent des sorties',
      (await page.locator('.vb--cours').count()) > 0);
    // La dernière séance du jeudi est annulée : la sortie est 16:50, pas 17:45.
    const finJeudi = await page.evaluate(() => {
      const seg = window.segmentsCours('narek', window.ttState.week, 'Jeudi', window.grilleDePronote('narek'));
      return seg.length ? seg[seg.length - 1].fin : null;
    });
    verifier('la sortie du jeudi avance quand la dernière heure saute',
      finJeudi === 16 * 60 + 50, String(finJeudi));
    // Et la vue le montre : aucun bloc « Cours 17:45 » dans la colonne du jeudi.
    const blocJeudi = await page.evaluate(() => {
      const titres = [...document.querySelectorAll('.ovv__title')];
      const i = titres.findIndex((e) => /Jeudi/i.test(e.textContent));
      if (i === -1) return null;
      const col = String(i + 2);
      return [...document.querySelectorAll('.ovv__body')]
        .filter((e) => getComputedStyle(e).gridColumnStart === col)
        .map((e) => e.innerText.replace(/\n/g, ' '));
    });
    verifier('la colonne du jeudi ne montre plus 17:45',
      blocJeudi === null || !blocJeudi.some((t) => t.includes('17:45')), JSON.stringify(blocJeudi));

    // --- Avancer d'une semaine va chercher les séances de cette semaine-là ---
    await page.click('#vue-grille');
    await page.waitForTimeout(200);
    verifier('la matière de la semaine prochaine n’est pas dans celle-ci',
      !(await page.locator('#tt-grid').innerText()).includes('Latin la semaine prochaine'));
    await page.click('#wk-suiv');
    await page.waitForTimeout(300);
    verifier('elle apparaît quand on avance d’une semaine',
      (await page.locator('#tt-grid').innerText()).includes('Latin la semaine prochaine'),
      (await page.locator('#wk-quoi').innerText()).replace(/\n/g, ' '));
    verifier('la semaine prochaine vient aussi de PRONOTE',
      (await page.locator('#tt-regime').innerText()).includes('PRONOTE'),
      await page.locator('#tt-regime').innerText());
    await page.click('#wk-retour');
    await page.waitForTimeout(250);

    // --- « Aujourd'hui » lit PRONOTE, pas le décalque ---
    await page.click('#tab-semaine');
    await page.waitForTimeout(300);
    verifier('le bloc « Aujourd’hui » est là', await page.locator('#jour-carte').isVisible());
    const carte = await page.locator('#jour-carte').innerText();
    verifier('il nomme la semaine de garde', /semaine\s+(Papa|Mama)/.test(carte), carte.replace(/\n/g, ' | '));
    verifier('il ne se réclame pas de septembre quand PRONOTE a parlé',
      !/emploi du temps de septembre/.test(carte), carte.replace(/\n/g, ' | '));
    verifier('il donne une heure de sortie', /collège\s+\d\d:\d\d\s*→\s*\d\d:\d\d/.test(carte),
      carte.replace(/\n/g, ' | '));

    verifier('aucune erreur de script', erreurs.length === 0, erreurs.slice(0, 5).join(' | '));
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
