import * as os from 'node:os';

function formatGiB(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(2)} GiB`;
}

const info: Record<string, string | number> = {
  Hostname: os.hostname(),
  'Operating system': `${os.type()} ${os.release()}`,
  Architecture: os.arch(),
  'Node.js': process.version,
  'Logical CPUs': os.cpus().length,
  'Total memory': formatGiB(os.totalmem()),
  'Free memory': formatGiB(os.freemem()),
  'System uptime': `${(os.uptime() / 3600).toFixed(2)} hours`,
};

console.log('System information');
for (const [label, value] of Object.entries(info)) {
  console.log(`${label}: ${value}`);
}
