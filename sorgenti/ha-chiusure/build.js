/* Chiusure2 compatta: due colonne, stessi comandi, nessun banner.
 * Uso: node build.js originale.json chiusure2.json
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
const none = { action: 'none' };
function grid(cards) { return { type: 'horizontal-stack', cards }; }
function full(card) { return { ...card, grid_options: { columns: 12, rows: 'auto' } }; }
function text(content) {
  return { type: 'markdown', content, card_mod: {
    style: {
      '.': 'ha-card { background: transparent !important; border: 0 !important; box-shadow: none !important; border-radius: 0 !important; } ha-markdown { padding: 3px 4px !important; font-size: 12px !important; line-height: 1.45 !important; }',
      'ha-markdown $': 'p { margin: 2px 0 !important; } h1,h2,h3 { font-size: 12px !important; margin: 0 !important; }',
    },
  } };
}
function button(source, name, icon, height = 34) {
  const card = {
    type: 'custom:button-card',
    name: name ?? source.name,
    icon: icon ?? source.icon,
    show_icon: true, show_name: true, show_state: false,
    tap_action: copy(source.tap_action ?? none),
    styles: {
      card: [{ height: `${height}px`, padding: '3px 2px', 'border-radius': '7px', border: 'none', 'box-shadow': 'none', background: 'var(--secondary-background-color)' }],
      grid: [{ 'grid-template-areas': '"i n"', 'grid-template-columns': '20px 1fr' }],
      icon: [{ width: '17px', color: 'var(--primary-color)' }],
      name: [{ 'font-size': '11px', 'font-weight': '500', 'white-space': 'nowrap', 'justify-self': 'center' }],
    },
  };
  for (const key of ['entity', 'hold_action', 'double_tap_action', 'icon_tap_action', 'confirmation']) {
    if (source[key] !== undefined) card[key] = copy(source[key]);
  }
  return card;
}
function actions(source, names, icons) {
  assert.equal(source.cards[1].cards.length, names.length);
  return grid(source.cards[1].cards.map((c, i) => button(c, names[i], icons[i])));
}
function room(source, frangisole) {
  const controls = copy(source.cards[0]);
  // Conserva esattamente la riga cover nativa: nome, posizione e comandi.
  controls.show_header_toggle = false;
  controls.card_mod = {
    style: 'ha-card { padding: 0 !important; background: transparent !important; box-shadow: none !important; border: 0 !important; border-radius: 0 !important; } #states { padding: 0 4px !important; } hui-cover-entity-row { --mdc-icon-button-size: 32px; --mdc-icon-size: 20px; font-size: 12px; }',
  };
  const presets = source.cards[1].cards;
  const names = frangisole
    ? ['Su ×2', 'Su', 'Orizz.', 'Giù', 'Giù ×2']
    : presets.map(c => c.name === 'LAMELLE ORIZZONTALI' ? 'Lamelle' : c.name);
  const icons = frangisole
    ? ['mdi:chevron-double-up', 'mdi:chevron-up', 'mdi:blinds-horizontal', 'mdi:chevron-down', 'mdi:chevron-double-down']
    : ['mdi:blinds-horizontal', 'mdi:window-shutter', 'mdi:window-shutter'];
  return full({
    type: 'vertical-stack',
    card_mod: { style: ':host { --stack-card-gap: 1px; }' },
    cards: [controls, grid(presets.map((c, i) => button(c, names[i], icons[i])))],
  });
}
const weather = first[1].cards.map((c, i) => {
  const result = button(c, ['Sole', 'Nuvole', 'Pioggia'][i], undefined, 42);
  result.styles.grid = [{ 'grid-template-areas': '"i" "n"', 'grid-template-columns': '1fr', 'grid-template-rows': '20px 14px' }];
  const option = c.tap_action.service_data.option;
  result.state = [{ value: option, styles: {
    card: [{ background: 'var(--primary-color)' }],
    icon: [{ color: 'var(--text-primary-color)' }],
    name: [{ color: 'var(--text-primary-color)' }],
  } }];
  return result;
});
const auto = button(first[3].cards[1].cards[0], 'Automatiche', 'mdi:blinds-horizontal', 42);
auto.show_label = true;
auto.label = "[[[ return entity?.state === 'on' ? 'ATTIVE' : 'SOSPESE'; ]]]";
auto.styles.grid = [{ 'grid-template-areas': '"n" "l"', 'grid-template-columns': '1fr', 'grid-template-rows': '18px 14px' }];
auto.show_icon = false;
auto.styles.label = [{ 'font-size': '10px', color: 'var(--secondary-text-color)' }];
auto.state = [{ value: 'on', styles: { name: [{ color: 'var(--primary-color)' }] } }];
const garden = button(first[0], 'Giardino', 'mdi:sprinkler-variant', 38);
garden.state = [{ value: 'on', styles: { icon: [{ color: 'var(--green-color, #4caf50)' }] } }];
const garage = button(first[2], 'Sezionale', 'mdi:garage', 38);
garage.show_label = true;
garage.label = "[[[ return entity?.state === 'on' ? 'COMANDO ATTIVO' : 'APRI / CHIUDI'; ]]]";
garage.styles.grid = [{ 'grid-template-areas': '"n" "l"', 'grid-template-columns': '1fr', 'grid-template-rows': '16px 13px' }];
garage.styles.label = [{ 'font-size': '9px', color: 'var(--secondary-text-color)' }];
garage.show_icon = false;
function routine(source, name, icon) {
  return button({ entity: source.entity, tap_action: { action: 'perform-action', perform_action: 'script.turn_on', target: { entity_id: source.entity } }, hold_action: { action: 'more-info' } }, name, icon, 38);
}
const scheduleOriginal = first[4].content;
assert(scheduleOriginal.includes('CHIUSURE AUTOMATICHE:'));
const prefix = scheduleOriginal.split('CHIUSURE AUTOMATICHE:')[0];
const schedule = text(prefix +
  `**{{ fase }}** · {{ now().strftime('%d/%m %H:%M') }}<br>\n` +
  `Alba **{% if alba_valida %}{{ alba.strftime('%H:%M') }}{% else %}n/d{% endif %}** · Apertura **{% if mattina_valida %}{{ apertura_ordinaria.strftime('%H:%M') }}{% else %}n/d{% endif %}** · Notte **{% if notte_valida %}{{ nilan_notturna.strftime('%H:%M') }}{% else %}n/d{% endif %}**<br>\n` +
  `Fine giorno **{% if crepuscolo_valido %}{{ fine_giornaliero.strftime('%H:%M') }}{% else %}n/d{% endif %}** · Serale **{% if crepuscolo_valido %}{{ inizio_serale.strftime('%H:%M') }}–{{ fine_serale.strftime('%H:%M') }}{% else %}n/d{% endif %}**<br>\n` +
  `Crepuscolo **{% if crepuscolo_valido %}{{ crepuscolo.strftime('%H:%M') }}{% else %}n/d{% endif %}**<br>\n` +
  `<small>Fine giorno −1h40 · Inizio serale −1h35 · Fine serale +5 min dal crepuscolo.</small>`);
const overview = text('**Piano terra**<br>\n' + first[3].cards[0].content);
const attic = text('**Sottotetto**<br>\n' + first[3].cards[1].cards[1].content.replace(/(?:<br>\s*){2,}/g, '<br> '));
const result = {
  ...copy(original),
  title: 'Chiusure2', path: 'chiusure2', max_columns: 2,
  dense_section_placement: false,
  sections: [
    { type: 'grid', column_span: 1, cards: [
      full(grid([...weather, auto])),
      full(grid([garden, garage, routine(first[5], 'Risveglio', 'mdi:weather-sunset-up'), routine(first[6], 'Tutti svegli', 'mdi:weather-sunny')])),
      full(text('**FRANGISOLE**')),
      full(actions(first[7], ['Apri', 'Ferma', 'Frangi', 'Chiudi'], ['mdi:arrow-up', 'mdi:stop', 'mdi:blinds-horizontal', 'mdi:arrow-down'])),
      ...first.slice(10, 14).map(c => room(c, true)),
      full(schedule),
    ] },
    { type: 'grid', column_span: 1, cards: [
      full(text('**AVVOLGIBILI**')),
      full(actions(first[8], ['Apri', 'Ferma', 'Chiudi'], ['mdi:arrow-up', 'mdi:stop', 'mdi:arrow-down'])),
      ...second.slice(1, 7).map(c => room(c, false)),
      full(grid([overview, attic])),
    ] },
  ],
};
delete result.cards;
function walk(value, fn) {
  if (value && typeof value === 'object') {
    fn(value);
    for (const child of Object.values(value)) walk(child, fn);
  }
}
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
let covers = 0, jsCount = 0;
walk(result, obj => {
  if (Array.isArray(obj.entities) && obj.entities.some(r => r.entity?.startsWith('cover.') && r.secondary_info === 'position')) covers++;
  for (const val of Object.values(obj)) {
    if (typeof val === 'string' && val.trim().startsWith('[[[') && val.trim().endsWith(']]]')) {
      new Function('entity', 'states', 'hass', val.trim().slice(3, -3));
      jsCount++;
    }
  }
});
assert.equal(covers, 10);
assert.equal(result.sections.length, 2);
assert(result.sections.every(s => s.column_span === 1));
fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ columns: result.max_columns, sections: result.sections.length, covers, preserved_actions: oldActions.size, javascript_templates: jsCount, bytes: fs.statSync(output).size }));
