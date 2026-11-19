import readline from 'node:readline';
import path from 'node:path';
import {EventEmitter} from 'node:events';
import {plugin_init, plugin_onmessage, plugin_cleanup} from './index.mjs';

// Private stdio transport. Only the parent AstrBot process can submit work.
const dataPath = process.argv[2];
const routes = new Map();
const pending = new Map();
const leases = new Map();
let serial = 0;
const write = packet => process.stdout.write(JSON.stringify(packet) + '\n');
function action(method, params) {
  const actionId = ++serial;
  return new Promise((resolve, reject) => {
    pending.set(actionId, {resolve, reject});
    write({actionId, method, params});
  });
}
const ctx = {
  dataPath, configPath: path.join(dataPath, 'config.json'),
  logger: Object.fromEntries(['info','warn','error','debug'].map(level =>
    [level, message => write({level, message})])),
  actions: {call: action}, pluginManager: {config: {}},
  router: {static() {}, page() {},
    get: (url, handler) => routes.set('GET ' + url, handler),
    post: (url, handler) => routes.set('POST ' + url, handler)}
};
async function handle(packet) {
  if (packet.actionId) {
    const promise = pending.get(packet.actionId);
    pending.delete(packet.actionId);
    if (packet.error) promise?.reject(new Error(packet.error));
    else promise?.resolve(packet.result);
    return;
  }
  const {id, method, args} = packet;
  try {
    let result;
    if (method === 'init') {
      await plugin_init(ctx);
      result = [...routes.keys()];
    } else if (method === 'message') await plugin_onmessage(ctx, args);
    else if (method === 'close') await plugin_cleanup(ctx);
    else if (method === 'release') {
      leases.get(args)?.emit('finish');
      leases.delete(args);
    } else if (method === 'web') {
      const handler = routes.get(args.route);
      if (!handler) throw new Error('未知接口');
      const raw = new EventEmitter();
      const res = {
        raw, code: 200, setHeader() {}, status(code) { this.code = code; return this; },
        json(body) { result = {body, status: this.code}; },
        sendFile(file) { leases.set(id, raw); result = {file, lease: id}; }
      };
      await handler({body: args.body, params: args.params}, res);
    } else throw new Error('未知请求');
    write({id, result: result ?? null});
  } catch (err) {
    write({id, error: String(err.message)});
  }
}
const lines = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
lines.on('line', line => { void handle(JSON.parse(line)); });
lines.on('close', () => process.exit(0));
