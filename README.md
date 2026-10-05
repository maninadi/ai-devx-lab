# System information

A minimal TypeScript Node.js project that prints information about the host system.
It uses Node's built-in APIs and has no runtime dependencies.

## Requirements

- Node.js 22 or newer
- npm

## Install and run

```sh
npm install
npm start
```

`npm start` compiles the TypeScript source and runs the generated JavaScript.
The script prints the hostname, OS version, architecture, Node.js version,
logical CPU count, total and free memory in GiB, and system uptime in hours.
Values reflect the environment running the script, including any container limits
or host information exposed by that environment.

## Other commands

```sh
npm run check  # Type-check without generating files
npm run build  # Compile into dist/
node dist/system-info.js  # Run an existing build
```

Source code lives in `src/system-info.ts`. Compiler settings live in
`tsconfig.json`. Generated output and installed dependencies are ignored by Git.
The lockfile records dependency versions; use `npm ci` for reproducible installs.
