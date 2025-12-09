const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/masseyferguson/customer/en_GB/wholegoods/products';
const OUTPUT_FILE = 'agco_complete_data.json';
const MAX_CONCURRENCY = 5; // Keep 5 for stability with heavy scraping
const MAX_DEPTH = 6;
const MAX_RETRIES = 3;

// --- COLORS ---
const CLR = {
    Reset: "\x1b[0m",
    Green: "\x1b[32m",
    Yellow: "\x1b[33m",
    Cyan: "\x1b[36m",
    Red: "\x1b[31m"
};

// --- STATE ---
const queue = [];
const results = [];
const visited = new Set();
let activeWorkers = 0;

// --- HELPERS ---
const wait = (ms) => new Promise(r => setTimeout(r, ms));

async function waitForAngular(page) {
    try {
        await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 });
    } catch(e) {}
    await wait(1000);
}

// --- MAIN ---
(async () => {
    console.log(`${CLR.Green}======================================================${CLR.Reset}`);
    console.log(`${CLR.Green}   🚀 LAUNCHING SWARM V4 (FULL DATA EXTRACTION)   ${CLR.Reset}`);
    console.log(`${CLR.Green}======================================================${CLR.Reset}`);

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        protocolTimeout: 0,
        args: ['--start-maximized', '--disable-notifications']
    });

    // 1. Create Workers
    const workers = [];
    for (let i = 0; i < MAX_CONCURRENCY; i++) {
        const page = await browser.newPage();

        // Block only heavy media to keep descriptions/layout intact
        await page.setRequestInterception(true);
        page.on('request', (req) => {
            if (['image', 'media'].includes(req.resourceType())) req.abort();
            else req.continue();
        });

        workers.push({ id: i + 1, page });
    }

    // 2. Start
    queue.push({ url: BASE_URL, depth: 0, parent: "ROOT", retryCount: 0 });

    // 3. Monitor
    const monitor = setInterval(() => {
        console.log(`${CLR.Yellow}[STATUS] Active: ${activeWorkers}/${MAX_CONCURRENCY} | Queue: ${queue.length} | Items Scraped: ${results.length}${CLR.Reset}`);
    }, 2000);

    // 4. Distributor
    while (queue.length > 0 || activeWorkers > 0) {
        while (queue.length > 0 && workers.length > 0) {
            const task = queue.shift();

            const taskKey = `${task.url}::${task.depth}`;
            if (visited.has(taskKey) && task.retryCount === 0) continue;
            visited.add(taskKey);

            const worker = workers.pop();
            activeWorkers++;

            processTask(worker, task).then((w) => {
                workers.push(w);
                activeWorkers--;
            });
        }
        await wait(200);
    }

    clearInterval(monitor);

    console.log(`${CLR.Green}\n✅ DONE! Saved ${results.length} items to ${OUTPUT_FILE}.${CLR.Reset}`);
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));
    await browser.close();
})();

// --- WORKER LOGIC ---
async function processTask(worker, task) {
    const { id, page } = worker;
    const { url, depth, parent, retryCount } = task;
    const logPrefix = `${CLR.Cyan}[W${id}]${CLR.Reset}`;

    try {
        // A. Navigate
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });

        // B. Handle Cookies
        const cookieBtn = await page.$('#truste-consent-button');
        if (cookieBtn) await cookieBtn.click().catch(()=>{});

        await waitForAngular(page);

        // C. Find Selectors
        let selector = '';
        try {
            await page.waitForFunction(() =>
                document.querySelector('.brand-card-group') ||
                document.querySelector('app-cpq-product-card') ||
                document.querySelector('.product-item'),
                { timeout: 10000 }
            );
        } catch(e) {}

        if (await page.$('.brand-card-group')) selector = '.brand-card-group';
        else if (await page.$('app-cpq-product-card')) selector = 'app-cpq-product-card';
        else selector = '.product-item';

        // D. SCRAPE EVERYTHING (Deep Extraction)
        const items = await page.evaluate((sel) => {
            return Array.from(document.querySelectorAll(sel)).map(el => {
                // 1. Title
                const tEl = el.querySelector('.card-title, h4, h3');
                const titleText = tEl ? tEl.innerText.trim() : "";

                // 2. Image
                const imgEl = el.querySelector('img');
                const imgSrc = imgEl ? imgEl.src : "";
                const imgAlt = imgEl ? imgEl.alt : "";

                // 3. Description (The important part)
                // We look for paragraph tags or specific description classes
                const descEl = el.querySelector('.card-text, .description, p.text-muted');
                const description = descEl ? descEl.innerText.trim() : "";

                // 4. Leaf Check
                const isLeaf = !!el.querySelector('input[type="checkbox"], .chk');

                // Fallback for Title
                const finalTitle = titleText || imgAlt || "Unknown Product";

                return {
                    title: finalTitle,
                    description: description,
                    image_url: imgSrc,
                    isLeaf: isLeaf
                };
            });
        }, selector);

        if (items.length > 0) {
            console.log(`${logPrefix} Found ${items.length} items in "${parent}"`);

            for (let i = 0; i < items.length; i++) {
                const item = items[i];

                // SAVE FULL DATA
                results.push({
                    parent: parent,
                    depth: depth,
                    url: url,
                    title: item.title,
                    description: item.description,
                    image: item.image_url
                });

                // RECURSION (Drill Down)
                if (!item.isLeaf && depth < MAX_DEPTH) {
                    console.log(`${logPrefix} 🖱️ Clicking ${i+1}/${items.length}: "${item.title}"`);

                    const freshCards = await page.$$(selector);
                    const target = freshCards[i];

                    if (target) {
                        const clicker = await target.$('img') || target;
                        await clicker.click();
                        await waitForAngular(page);

                        const newUrl = page.url();
                        if (newUrl !== url) {
                            queue.push({ url: newUrl, depth: depth + 1, parent: item.title, retryCount: 0 });
                            await page.goBack({ waitUntil: 'domcontentloaded' });
                            await waitForAngular(page);
                        }
                    }
                }
            }
        } else {
            // Retry Logic for empty pages
            if (depth < 2 && retryCount < MAX_RETRIES) {
                console.log(`${logPrefix} ${CLR.Red}0 items. Retrying (${retryCount+1})...${CLR.Reset}`);
                queue.push({ ...task, retryCount: retryCount + 1 });
            }
        }

    } catch (e) {
        console.log(`${logPrefix} ${CLR.Red}Error: ${e.message.split('\n')[0]}${CLR.Reset}`);
        if (retryCount < MAX_RETRIES) {
            queue.push({ ...task, retryCount: retryCount + 1 });
        }
    }

    return worker;
}