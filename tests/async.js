// An engine must not consult application-specific Promise reaction hooks.
globalThis.__renkuBindAsync = () => { throw Error('Unexpected engine ownership hook'); };
let resolve;
const shared = new Promise(r => resolve = r), observed = [];
async function work(label) {
  await shared;
  observed.push(label);
  await Promise.resolve();
  try { await Promise.reject(label); } catch (reason) { observed.push(reason + '-rejected'); }
  finally { observed.push(label + '-finally'); }
}
work('a'); work('b'); resolve();
Promise.resolve().then(() => {}).then(() => {}).then(() => {}).then(() => {}).then(() => {
  if (JSON.stringify(observed) !== '["a","b","a-rejected","a-finally","b-rejected","b-finally"]') throw Error(JSON.stringify(observed));
  if (new Intl.NumberFormat('en-US').format(1234) !== '1,234') throw Error('Intl unavailable');
  const closures = [];
  for (let index = 0; index < 3; index++) closures.push(() => index);
  if (JSON.stringify(closures.map(read => read())) !== '[0,1,2]') throw Error('Block scoping unavailable');
  print('renku-hermes unpatched async and Intl passed');
});
