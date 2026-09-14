// Read TypeScript syntax only; never execute application code or load credentials.
import {createRequire} from 'node:module';
import {readFileSync, readdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const ts = require('typescript');
const results = [];
function scan(dir) {
  for (const e of readdirSync(dir, {withFileTypes: true})) {
    const file = path.join(dir, e.name);
    if (e.isDirectory()) { scan(file); continue; }
    if (!/\.tsx?$/.test(file)) continue;
    const source = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    function walk(node, parent = '') {
      let next = parent;
      if (ts.isFunctionDeclaration(node) && node.name) {
        const name = node.name.text;
        const qualified = parent ? `${parent}.${name}` : name;
        results.push({file: path.relative(root, file), name: qualified,
          line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
          signature: `${name}(${node.parameters.map(p=>p.getText(source)).join(', ')})${node.type ? ': ' + node.type.getText(source) : ''}`});
        next = qualified;
      }
      ts.forEachChild(node, child => walk(child, next));
    }
    walk(source);
  }
}
scan(path.join(root, 'frontend/src'));
console.log(JSON.stringify(results));
