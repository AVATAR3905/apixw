const fs = require('fs');
const content = fs.readFileSync('C:\\Users\\cecilia\\Downloads\\APIx-main\\APIx-main\\apps\\dashboard\\src\\app\\forecast\\page.tsx', 'utf8');
let idx = content.indexOf('change: `');
while (idx >= 0) {
    console.log('Found at:', idx);
    console.log(content.substring(idx, idx+100));
    idx = content.indexOf('change: `', idx+1);
}