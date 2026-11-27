/* Crea Chiusure2 a partire dalla sola vista Chiusure esportata da HA.
 * Uso: node build.js originale.json chiusure2.json
 * Non modifica la vista di origine e conserva le azioni esistenti.
 */
'use strict';
const fs = require('node:fs');
const assert = require('node:assert/strict');
const [input, output] = process.argv.slice(2);
assert(input && output, 'Uso: node build.js originale.json chiusure2.json');
const original = JSON.parse(fs.readFileSync(input, 'utf8'));
assert.equal(original.path, 'chiusure');
const copy = value => JSON.parse(JSON.stringify(value));
const first = original.sections[0].cards;
const second = original.sections[1].cards;
const palette = {
  accent: 'var(--primary-color)',
  surface: 'var(--ha-card-background, var(--card-background-color))',
  soft: 'var(--secondary-background-color)',
  text: 'var(--primary-text-color)',
  muted: 'var(--secondary-text-color)',
};
const surface = {
  'border-radius': '20px',
  'box-shadow': 'none',
  border: '1px solid var(--divider-color)',
  background: palette.surface,
};
const noAction = { action: 'none' };
function header(text, icon) {
  return { type: 'heading', heading: text, icon, heading_style: 'title' };
}
function button(source, name, icon, compact = false) {
  const card = {
    type: 'custom:button-card',
    name: name ?? source.name,
    icon: icon ?? source.icon,
    show_icon: true,
    show_name: true,
    show_state: false,
    tap_action: copy(source.tap_action ?? noAction),
    styles: {
      card: [surface, { padding: compact ? '10px 4px' : '14px 8px' }],
      icon: [{ width: compact ? '21px' : '25px', color: palette.accent }],
      name: [{ 'font-size': compact ? '11px' : '12px', 'font-weight': '500', 'white-space': 'normal', 'margin-top': '6px' }],
    },
  };
  for (const key of ['entity', 'hold_action', 'double_tap_action', 'confirmation']) {
    if (source[key] !== undefined) card[key] = copy(source[key]);
  }
  return card;
}
function grid(cards, columns) {
  return { type: 'grid', columns, square: false, cards };
}
function full(card, columns = 12) {
  return { ...card, grid_options: { columns, rows: 'auto' } };
}
function actions(group, names, icons) {
  const cards = group.cards[1].cards;
  assert.equal(cards.length, names.length);
  return grid(cards.map((c, i) => button(c, names[i], icons[i], true)), cards.length);
}
const ids = {
  'cover.sonoff_100216eb23': { name: 'Matrimoniale', floor: 'Piano terra', sun: [160, 300], tint: '#c86b67' },
  'cover.sonoff_10024ca6a7': { name: 'Cucina', floor: 'Piano terra', sun: [160, 300], tint: '#c86b67' },
  'cover.sonoff_10024c93f3': { name: 'Divano', floor: 'Piano terra', sun: [90, 180], tint: '#68a581' },
  'cover.sonoff_10024ca61a': { name: 'Studio', floor: 'Piano terra', sun: [90, 180], tint: '#68a581' },
  'cover.sonoff_100216eb2a': { name: 'Leo', floor: 'Piano terra', sun: [230, 300], tint: '#c9955f' },
  'cover.sonoff_10024cb235': { name: 'Ale', floor: 'Piano terra', sun: [90, 180], tint: '#729dca' },
  'cover.sonoff_10024cbecb': { name: 'Bagno', floor: 'Piano terra', sun: [90, 180], tint: '#729dca' },
  'cover.sonoff_10024cbd82': { name: 'Lavanderia', floor: 'Piano terra', sun: [60, 110], tint: '#729dca' },
  'cover.avolgibile_sottotetto': { name: 'Sottotetto', floor: 'Sottotetto', sun: [160, 300], tint: '#c86b67' },
  'cover.sonoff_1002605154': { name: 'Scala', floor: 'Sottotetto', sun: [230, 300], tint: '#c9955f' },
};
function room(source, frangisole) {
  const entityRow = source.cards[0].entities[0];
  const entity = entityRow.entity;
  const meta = ids[entity];
  assert(meta, `Chiusura non censita: ${entity}`);
  const controls = copy(source.cards[0]);
  controls.entities[0].name = 'Posizione';
  controls.show_header_toggle = false;
  controls.state_color = true;
  const presetSource = source.cards[1].cards;
  const names = frangisole
    ? ['Su ×2', 'Su', 'Orizzontali', 'Giù', 'Giù ×2']
    : presetSource.map(c => c.name === 'LAMELLE ORIZZONTALI' ? 'Lamelle 20%' : c.name);
  const icons = frangisole
    ? ['mdi:chevron-double-up', 'mdi:chevron-up', 'mdi:blinds-horizontal', 'mdi:chevron-down', 'mdi:chevron-double-down']
    : ['mdi:blinds-horizontal', 'mdi:window-shutter', 'mdi:window-shutter'];
  const sun = `[[[ const az = Number(states['sun.sun']?.attributes?.azimuth); if (!Number.isFinite(az)) return 'Sole n/d'; return az >= ${meta.sun[0]} && az <= ${meta.sun[1]} ? '☀️ Al sole' : '◌ In ombra'; ]]]`;
  return full({
    type: 'custom:button-card',
    entity,
    name: meta.name,
    show_icon: false,
    show_name: true,
    show_label: true,
    label: `${meta.floor} · ${frangisole ? 'Frangisole' : 'Avvolgibile'}`,
    tap_action: noAction,
    hold_action: { action: 'more-info' },
    triggers_update: ['sun.sun', entity],
    custom_fields: {
      sun,
      cover: { card: controls },
      presets: { card: grid(presetSource.map((c, i) => button(c, names[i], icons[i], true)), names.length) },
    },
    styles: {
      card: [surface, { padding: '16px 12px 12px', 'pointer-events': 'auto', 'border-left': `3px solid ${meta.tint}` }],
      grid: [{ 'grid-template-areas': '"n sun" "l l" "cover cover" "presets presets"', 'grid-template-columns': '1fr auto', 'grid-template-rows': 'min-content min-content min-content min-content', 'row-gap': '5px' }],
      name: [{ 'justify-self': 'start', 'font-size': '17px', 'font-weight': '600', color: palette.text }],
      label: [{ 'justify-self': 'start', 'font-size': '11px', color: palette.muted }],
      custom_fields: {
        sun: [{ 'font-size': '11px', color: palette.muted, 'justify-self': 'end' }],
        cover: [{ '--ha-card-background': 'transparent', '--card-background-color': 'transparent', '--ha-card-border-width': '0px', '--ha-card-box-shadow': 'none' }],
        presets: [{ 'padding-top': '3px' }],
      },
    },
  });
}
const weather = grid(first[1].cards.map((c, i) => {
  const result = button(c, ['Sole', 'Nuvoloso', 'Pioggia'][i]);
  const option = c.tap_action.service_data.option;
  result.state = [{ value: option, styles: {
    card: [{ background: 'var(--primary-color)', border: '1px solid var(--primary-color)' }],
    icon: [{ color: 'var(--text-primary-color)' }],
    name: [{ color: 'var(--text-primary-color)' }],
  } }];
  return result;
}), 3);
const automation = button(first[3].cards[1].cards[0], 'Chiusure automatiche', 'mdi:blinds-horizontal');
automation.show_label = true;
automation.label = "[[[ return entity?.state === 'on' ? 'Attive · tocca per sospendere' : 'Sospese · tocca per attivare'; ]]]";
automation.styles.grid = [{ 'grid-template-areas': '"i n" "i l"', 'grid-template-columns': '40px 1fr' }];
automation.styles.name = [{ 'justify-self': 'start', 'font-size': '14px', 'font-weight': '500' }];
automation.styles.label = [{ 'justify-self': 'start', 'font-size': '11px', color: palette.muted, 'margin-top': '5px' }];
automation.styles.icon = [{ width: '25px', color: "[[[ return entity?.state === 'on' ? 'var(--primary-color)' : 'var(--secondary-text-color)'; ]]]" }];
const garden = copy(first[0]);
garden.name = 'Giardino';
garden.vertical = false;
const garage = copy(first[2]);
garage.name = 'Sezionale';
garage.styles.card = [surface, { padding: '12px', height: '76px' }];
garage.styles.icon = [{ width: '30px' }];
garage.styles.name = [{ 'font-size': '14px', 'font-weight': '500', 'justify-self': 'start' }];
garage.styles.state = [{ 'font-size': '10px', 'justify-self': 'start', color: palette.muted }];
const hero = full({
  type: 'custom:button-card',
  name: 'Chiusure2',
  label: 'Luce, privacy e comandi della casa',
  icon: 'mdi:window-shutter',
  show_label: true,
  tap_action: noAction,
  styles: {
    card: [{ background: 'none', border: 'none', 'box-shadow': 'none', padding: '8px 0 12px' }],
    grid: [{ 'grid-template-areas': '"i n" "i l"', 'grid-template-columns': '44px 1fr' }],
    icon: [{ width: '30px', color: palette.accent }],
    name: [{ 'justify-self': 'start', 'font-size': '26px', 'font-weight': '600' }],
    label: [{ 'justify-self': 'start', 'font-size': '12px', color: palette.muted, 'margin-top': '6px' }],
  },
});
const schedule = copy(first[4]);
schedule.title = 'Il programma di oggi';
const marker = 'CHIUSURE AUTOMATICHE:';
assert(schedule.content.includes(marker));
schedule.content = schedule.content.split(marker)[0] +
  `### {{ fase }}\n` +
  `{{ now().strftime('%d/%m/%Y · %H:%M') }}\n\n` +
  `| Momento | Orario |\n|:--|--:|\n` +
  `| Alba | {% if alba_valida %}{{ alba.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n` +
  `| Apertura ordinaria | {% if mattina_valida %}{{ apertura_ordinaria.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n` +
  `| Fine giornaliero | {% if crepuscolo_valido %}{{ fine_giornaliero.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n` +
  `| Inizio serale | {% if crepuscolo_valido %}{{ inizio_serale.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n` +
  `| Crepuscolo | {% if crepuscolo_valido %}{{ crepuscolo.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n` +
  `| Fine serale | {% if crepuscolo_valido %}{{ fine_serale.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n` +
  `| Chiusura ordinaria | {% if notte_valida %}{{ nilan_notturna.strftime('%H:%M') }}{% else %}n/d{% endif %} |\n\n` +
  `Fine giornaliero: 1h40 prima del crepuscolo. Inizio serale: 1h35 prima. Fine serale: circa 5 minuti dopo.\n`;
const overview = copy(first[3].cards[0]);
overview.title = 'Piano terra · posizioni';
const attic = copy(first[3].cards[1].cards[1]);
attic.title = 'Sottotetto · posizioni e sole';
const result = {
  ...copy(original),
  title: 'Chiusure2',
  path: 'chiusure2',
  icon: 'mdi:window-shutter',
  type: 'sections',
  max_columns: 3,
  dense_section_placement: true,
  sections: [
    { type: 'grid', column_span: 3, cards: [
      hero,
      full(weather, 6), full(automation, 6),
      full(grid([garden, garage], 2), 6),
      full(grid([copy(first[5]), copy(first[6])], 2), 6),
      full({ type: 'vertical-stack', cards: [header('Tutti i frangisole', 'mdi:blinds-horizontal'), actions(first[7], ['Apri', 'Ferma', 'Frangi', 'Chiudi'], ['mdi:arrow-up', 'mdi:stop', 'mdi:blinds-horizontal', 'mdi:arrow-down'])] }, 6),
      full({ type: 'vertical-stack', cards: [header('Tutti gli avvolgibili', 'mdi:window-shutter'), actions(first[8], ['Apri', 'Ferma', 'Chiudi'], ['mdi:arrow-up', 'mdi:stop', 'mdi:arrow-down'])] }, 6),
    ] },
    { type: 'grid', cards: [header('Frangisole', 'mdi:blinds-horizontal'), ...first.slice(10, 14).map(c => room(c, true))] },
    { type: 'grid', cards: [header('Avvolgibili', 'mdi:window-shutter'), ...second.slice(1, 7).map(c => room(c, false))] },
    { type: 'grid', cards: [header('Sole e orari', 'mdi:weather-sunset'), full(schedule), full(overview), full(attic)] },
  ],
};
delete result.cards;
function walk(value, fn) {
  if (value && typeof value === 'object') {
    fn(value);
    for (const child of Object.values(value)) walk(child, fn);
  }
}
// Confronta le azioni esplicite, senza interpretarle o sostituire target.
function actionSet(view) {
  const set = new Set();
  walk(view, card => {
    for (const key of ['tap_action', 'hold_action', 'double_tap_action', 'icon_tap_action']) {
      const a = card[key];
      if (a && a.action !== 'none') set.add(JSON.stringify(a));
    }
  });
  return set;
}
const oldActions = actionSet(original), newActions = actionSet(result);
assert.deepEqual([...oldActions].filter(x => !newActions.has(x)), [], 'Azioni originali mancanti');
// Anche le righe cover native devono mantenere entità e informazioni posizione.
for (const entity of Object.keys(ids)) {
  let found = false;
  walk(result, card => {
    if (Array.isArray(card.entities) && card.entities.some(r => r.entity === entity && r.secondary_info === 'position')) found = true;
  });
  assert(found, `Riga cover mancante: ${entity}`);
}
let jsCount = 0;
walk(result, obj => {
  for (const val of Object.values(obj)) {
    if (typeof val === 'string' && val.trim().startsWith('[[[') && val.trim().endsWith(']]]')) {
      new Function('entity', 'states', 'hass', val.trim().slice(3, -3));
      jsCount++;
    }
  }
});
fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ path: result.path, covers: Object.keys(ids).length, preserved_actions: oldActions.size, javascript_templates: jsCount, bytes: fs.statSync(output).size }));
