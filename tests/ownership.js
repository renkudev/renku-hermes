let current;
function withOwner(owner, callback) {
  const previous = current;
  current = owner;
  try { return callback(); } finally { current = previous; }
}
globalThis.__renkuBindAsync = callback => {
  if (!callback) return callback;
  const owner = current;
  return function (...args) { return withOwner(owner, () => callback.apply(this, args)); };
};
const a = { name: 'a', active: true }, b = { name: 'b', active: true };
let resolve;
const shared = new Promise(r => resolve = r), observed = [];
withOwner(a, async () => { await shared; observed.push(current.name); await Promise.resolve(); observed.push(current.active); });
withOwner(b, async () => { await shared; observed.push(current.name); try { await Promise.reject('test'); } catch { observed.push(current.name); } });
a.active = false;
withOwner(b, () => resolve());
Promise.resolve().then(() => {}).then(() => {}).then(() => {}).then(() => {
  if (JSON.stringify(observed) !== '["a","b",false,"b"]') throw Error(JSON.stringify(observed));
  if (new Intl.NumberFormat('en-US').format(1234) !== '1,234') throw Error('Intl unavailable');
  print('renku-hermes ownership and Intl passed');
});
