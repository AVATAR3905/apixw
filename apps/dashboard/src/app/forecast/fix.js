const fs = require('fs');
const content = fs.readFileSync('C:\\Users\\cecilia\\Downloads\\APIx-main\\APIx-main\\apps\\dashboard\\src\\app\\forecast\\page.tsx', 'utf8');
const idx = content.indexOf('change: `+${vsBasePct}%`');
console.log('Found at index:', idx);
if (idx >= 0) {
  console.log('Context:', content.substring(idx - 50, idx + 50));
}