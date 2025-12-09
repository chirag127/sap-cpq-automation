const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_swarm_dump.json';
const MAX_CONCURRENCY = 10; // 10 Browsers at once!
const MAX_DEPTH = 6;

// --- COLORS ---
const CLR = {
    Reset: "\x1b[0m",
    Red: "\x1b[31m",
    Green: "\x1b[32m",
    Yellow: "\x1b[33m",
    Blue: "\x1b[34m",
    Cyan: "\x1b[36m"
};

// --- SHARED STATE ---
const queue = [];
const results = [];
const visited = new Set();
let activeWorkers = 0;

// --- HELPERS ---
const wait = (ms) => new Promise(r => setTimeout(r, ms));

async function waitForAngular(page) {
    try {
        await page.waitForSelector('.loader-container', { hidden: true, timeout: 2000 });
    } catch(e) {}
    await wait(200); // Fast debounce
}

// --- MAIN ---
(async () => {
    console.log(`${CLR.Green}==================================================${CLR.Reset}`);
    console.log(`${CLR.Green}   🚀 LAUNCHING THE SWARM (${MAX_CONCURRENCY} WORKERS)   ${CLR.Reset}`);
    console.log(`${CLR.Green}==================================================${CLR.Reset}`);

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        protocolTimeout: 0,
        args: ['--start-maximized', '--disable-notifications']
    });

    // 1. Initialize Workers
    const workers = [];
    for (let i = 0; i < MAX_CONCURRENCY; i++) {
        const page = await browser.newPage();

        // TURBO MODE: Block EVERYTHING visual
        await page.setRequestInterception(true);
        page.on('request', (req) => {
            const type = req.resourceType();
            if (['image', 'font', 'stylesheet', 'media', 'other'].includes(type)) req.abort();
            else req.continue();
        });

        workers.push({ id: i + 1, page });
    }

    // 2. Start
    queue.push({ url: BASE_URL, depth: 0, parent: "ROOT" });

    // 3. Monitor Loop
    const monitor = setInterval(() => {
        console.log(`${CLR.Yellow}[STATUS] Active: ${activeWorkers}/${MAX_CONCURRENCY} | Queue: ${queue.length} | Found: ${results.length}${CLR.Reset}`);
    }, 2000);

    // 4. Task Distributor
    while (queue.length > 0 || activeWorkers > 0) {
        while (queue.length > 0 && workers.length > 0) {
            const task = queue.shift();

            if (visited.has(task.url)) continue;
            visited.add(task.url);

            const worker = workers.pop();
            activeWorkers++;

            // Run Async
            processTask(worker, task).then((w) => {
                workers.push(w);
                activeWorkers--;
            });
        }
        await wait(100);
    }

    clearInterval(monitor);

    console.log(`${CLR.Green}\n✅ SWARM FINISHED! Scraped ${results.length} items.${CLR.Reset}`);
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));
    console.log(`Data saved to: ${OUTPUT_FILE}`);
    await browser.close();
})();

// --- WORKER LOGIC ---
async function processTask(worker, task) {
    const { id, page } = worker;
    const { url, depth, parent } = task;
    const logPrefix = `${CLR.Cyan}[W${id}]${CLR.Reset}`;

    try {
        // Fast Timeout (20s) - Fail fast, don't hang
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });

        // Kill Cookie Banner (Once per load)
        const cookieBtn = await page.$('#truste-consent-button');
        if (cookieBtn) await cookieBtn.click().catch(()=>{});

        await waitForAngular(page);

        // Scan for Cards
        const selector = '.brand-card-group, app-cpq-product-card, .product-item, .card';
        // Quick check
        try {
            await page.waitForSelector(selector, { timeout: 3000 });
        } catch(e) {}

        const items = await page.evaluate((sel) => {
            return Array.from(document.querySelectorAll(sel)).map(el => {
                const t = el.querySelector('.card-title, h4, h3')?.innerText.trim();
                const img = el.querySelector('img')?.alt;
                const isLeaf = !!el.querySelector('input[type="checkbox"], .chk');
                return { title: t || img || "Unknown", isLeaf };
            });
        }, selector);

        if (items.length > 0) {
            console.log(`${logPrefix} Found ${items.length} items in "${parent}"`);

            // Process Items
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                results.push({ ...item, parent, depth, url });

                if (!item.isLeaf && depth < MAX_DEPTH) {
                    console.log(`${logPrefix} 🖱️ Clicking ${i+1}/${items.length}: ${item.title}`);

                    // Re-acquire DOM element
                    const freshCards = await page.$$(selector);
                    if (freshCards[i]) {
                        const target = freshCards[i];
                        const clicker = await target.$('img') || target;

                        await clicker.click();
                        await waitForAngular(page);

                        const newUrl = page.url();
                        if (newUrl !== url) {
                            // NEW LINK FOUND -> Add to Queue
                            queue.push({ url: newUrl, depth: depth + 1, parent: item.title });

                            // Go Back immediately to continue processing list
                            await page.goBack({ waitUntil: 'domcontentloaded' });
                            await waitForAngular(page);
                        }
                    }
                }
            }
        } else {
            // Leaf Page or Empty
            // console.log(`${logPrefix} Leaf Page.`);
        }

    } catch (e) {
        console.log(`${logPrefix} ${CLR.Red}Skip:${CLR.Reset} ${e.message.split('\n')[0]}`);
    }

    return worker;
}