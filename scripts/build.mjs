import {build,context} from 'esbuild';
import {cp,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
await mkdir(path.join(root,'frontend/dist'),{recursive:true});
await cp(path.join(root,'frontend/public'),path.join(root,'frontend/dist'),{recursive:true});
const options={absWorkingDir:root,entryPoints:['frontend/src/app.jsx'],bundle:true,outdir:'frontend/dist/assets',entryNames:'app',minify:!process.argv.includes('--watch'),sourcemap:false,define:{'process.env.NODE_ENV':'"production"'},target:['es2022'],logLevel:'info',legalComments:'eof'};
if(process.argv.includes('--watch')){const ctx=await context(options);await ctx.watch();console.log('Watching frontend/src. Refresh the browser after edits. Keep python run.py running.');}
else await build(options);
