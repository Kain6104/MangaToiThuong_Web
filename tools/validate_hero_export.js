const fs = require('fs');
const path = require('path');

const root = process.cwd();
const html = fs.readFileSync(path.join(root, 'heroes.html'), 'utf8');
const scriptTags = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/gi)];
const scriptErrors = [];
let scriptsChecked = 0;
scriptTags.forEach((match, index) => {
  if (/\bsrc=|application\/json/i.test(match[1]) || !match[2].trim()) return;
  scriptsChecked += 1;
  try {
    new Function(match[2]);
  } catch (error) {
    scriptErrors.push(`inline script ${index + 1}: ${error.message}`);
  }
});

const data = JSON.parse(fs.readFileSync(path.join(root, 'data', 'heroes.json'), 'utf8'));
const errors = [...scriptErrors];
const ids = new Set();
const codes = new Set();
const expectedRarityOrder = ['SSR', 'SR', 'SSS', 'SS', 'S', 'A', 'B'];
const internationalIds = new Set([
  1261449521, 1261449523, 1261449524, 1261450034, 1261450035, 1261450547,
  1261450548, 1261451057, 1261451061, 1261451062, 1261451063,
]);

for (const hero of data.heroes) {
  if (ids.has(String(hero.id))) errors.push(`duplicate id ${hero.id}`);
  if (codes.has(hero.code)) errors.push(`duplicate code ${hero.code}`);
  ids.add(String(hero.id));
  codes.add(hero.code);
  if (internationalIds.has(Number(hero.id))) {
    if (hero.sourceRegion !== 'international') errors.push(`${hero.code}: missing international provenance`);
    if (hero.rarity !== 'SR') errors.push(`${hero.code}: identity rarity must be SR`);
    if (hero.evidence?.identityLeader !== 15 || hero.evidence?.SSRCard !== 1) errors.push(`${hero.code}: invalid source rarity evidence`);
  }
  if (!Array.isArray(hero.skills) || !Array.isArray(hero.bonds) || !Array.isArray(hero.obtain)) errors.push(`${hero.code}: invalid array field`);
  if (!hero.stats || Array.isArray(hero.stats) || typeof hero.stats !== 'object') errors.push(`${hero.code}: invalid stats`);
  if (!/^\.\/img\/heros\/H\d{3}\.png$/.test(hero.image)) errors.push(`${hero.code}: invalid image path`);
  const image = path.join(root, hero.image.slice(2));
  const signature = fs.existsSync(image) ? fs.readFileSync(image).subarray(0, 8).toString('hex') : '';
  if (signature !== '89504e470d0a1a0a') errors.push(`${hero.code}: invalid PNG`);
  const manifest = path.join(root, hero.animation.manifest.slice(2));
  if (!fs.existsSync(manifest)) errors.push(`${hero.code}: missing manifest`);
  else {
    const manifestData = JSON.parse(fs.readFileSync(manifest, 'utf8'));
    const model = manifestData.model || {};
    for (const asset of [model.skeleton, model.atlas, ...(model.textures || [])].filter(Boolean)) {
      if (!fs.existsSync(path.join(root, asset.slice(2)))) errors.push(`${hero.code}: missing model asset ${asset}`);
    }
    const checkPaths = value => {
      if (Array.isArray(value)) return value.forEach(checkPaths);
      if (!value || typeof value !== 'object') return;
      if (typeof value.path === 'string' && value.path.startsWith('./') && !fs.existsSync(path.join(root, value.path.slice(2)))) {
        errors.push(`${hero.code}: missing manifest path ${value.path}`);
      }
      if (typeof value.src === 'string' && value.src.startsWith('./') && !fs.existsSync(path.join(root, value.src.slice(2)))) {
        errors.push(`${hero.code}: missing visual asset ${value.src}`);
      }
      Object.values(value).forEach(checkPaths);
    };
    checkPaths(manifestData);
  }
  if (!hero.visual?.enabled || hero.visual.manifest !== hero.animation.manifest) {
    errors.push(`${hero.code}: visual/animation manifest mismatch`);
  }
}

if (JSON.stringify(data.meta.rarityOrder) !== JSON.stringify(expectedRarityOrder)) {
  errors.push(`invalid rarity order ${JSON.stringify(data.meta.rarityOrder)}`);
}
if (data.heroes.filter(hero => hero.sourceRegion === 'international').length !== 11) errors.push('international roster count is not 11');

const output = {
  totalHeroes: data.heroes.length,
  metaTotalMatches: data.meta.totalHeroes === data.heroes.length,
  uniqueIds: ids.size,
  uniqueCodes: codes.size,
  scriptsChecked,
  scriptErrors: scriptErrors.length,
  errors,
};
console.log(JSON.stringify(output, null, 2));
process.exitCode = errors.length ? 1 : 0;
