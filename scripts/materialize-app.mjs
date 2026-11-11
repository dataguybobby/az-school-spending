import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

function materialize(name) {
  const source = path.join(root, "web", name);
  const dest = path.join(root, name);
  if (fs.existsSync(dest) || fs.lstatSync(dest, { throwIfNoEntry: false })) {
    fs.rmSync(dest, { recursive: true, force: true });
  }
  fs.cpSync(source, dest, { recursive: true, dereference: true });
}

materialize("src");
materialize("public");
console.log("copied web/src and web/public into the repository root");
