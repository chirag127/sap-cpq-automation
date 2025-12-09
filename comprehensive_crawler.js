const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_parallel_dump.json';
const MAX_CONCURRENCY = 5; // Number of simultaneous tabs (Don't go over 8)
const MAX_DEPTH = 6;

// --- SHARED STATE ---
const queue = [];           // URLs waiting to be scraped
const results = [];         // Final data
const visited = new Set();  // Deduplication
let activeWorkers = 0;      // Count of tabs currently busy

// --- MAIN ORCHESTRATOR ---
(async () => {
    console.log(`🚀 Launching Parallel Scraper with ${MAX_CONCURRENCY} workers...`);

    const browser = await puppeteer.launch({
        headless: false, // Keep visible to monitor
        defaultViewport: null,
        args: ['--start-maximized'],
        protocolTimeout: 0 // Prevent timeouts
    });

    // 1. Initialize Workers (Tabs)
    const workers = [];
    for (let i = 0; i < MAX_CONCURRENCY; i++) {
        const page = await browser.newPage();
        // Optimize page for speed
        await page.setRequestInterception(true);
        page.on('request', (req) => {
            // Block fonts/images to speed up loading
            if (['font', 'image'].includes(req.resourceType())) req.abort();
            else req.continue();
        });
        workers.push({ id: i + 1, page });
    }

    // 2. Setup Initial Queue (Home Page)
    queue.push({ url: BASE_URL, depth: 0, parent: "ROOT" });

    // 3. Start Processing Loop
    // We loop until the queue is empty AND no workers are busy
    while (queue.length > 0 || activeWorkers > 0) {

        // If queue has items and we have free workers, assign tasks
        while (queue.length > 0 && workers.length > 0) {
            const task = queue.shift();

            // Deduplicate
            if (visited.has(task.url)) continue;
            visited.add(task.url);

            const worker = workers.pop(); // Take a free worker
            activeWorkers++;

            // Process the task (Async - don't await here!)
            processTask(worker, task).then((returnedWorker) => {
                workers.push(returnedWorker); // Return worker to pool
                activeWorkers--;
            });
        }

        // Wait a tiny bit before checking again to save CPU
        await new Promise(r => setTimeout(r, 200));
    }

    // 4. Finish
    console.log("\n==================================================");
    console.log("✅ SCRAPING COMPLETE");
    console.log(`   Total Pages Visited: ${visited.size}`);
    console.log(`   Total Products Found: ${results.length}`);
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));
    console.log(`   Data saved to: ${OUTPUT_FILE}`);

    await browser.close();
})();

// --- WORKER LOGIC ---
async function processTask(worker, task) {
    const { id, page } = worker;
    const { url, depth, parent } = task;

    try {
        // console.log(`   [Worker ${id}] Visiting: ...${url.slice(-30)}`); // Verbose log

        // A. Navigate
        try {
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
        } catch(e) {
            console.log(`   ⚠️ [Worker ${id}] Timeout loading ${url}. Retrying once...`);
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
        }

        // B. Handle Cookies (Only needed once per tab really, but good safety)
        const cookieBtn = await page.$('#truste-consent-button');
        if (cookieBtn) await cookieBtn.click().catch(() => {});

        // C. Wait for Content
        await waitForContent(page);

        // D. Scrape Cards
        // We look for ANY card type
        const cardSelector = '.brand-card-group, app-cpq-product-card, .product-item, .card';
        const cards = await page.$$(cardSelector);

        if (cards.length > 0) {
            console.log(`   [Worker ${id}] Found ${cards.length} items at Depth ${depth}`);

            // Extract Data from all cards in parallel
            const items = await page.evaluate((sel) => {
                return Array.from(document.querySelectorAll(sel)).map(card => {
                    const t = card.querySelector('.card-title, h4, h3')?.innerText.trim() || "";
                    const img = card.querySelector('img');
                    const title = t || (img ? img.alt : "Unknown");

                    // Check for Checkbox (Leaf Node Indicator)
                    const isLeaf = !!card.querySelector('input[type="checkbox"], .chk');

                    // Attempt to find click destination (Deep Link)
                    // If no href, we flag it as needing a "Click" (which is harder in parallel)
                    // But usually, scraping the current URL + adding parameters helps
                    return { title, isLeaf };
                });
            }, cardSelector);

            // E. Process Results
            for (const item of items) {
                // Save Result
                results.push({
                    parent: parent,
                    title: item.title,
                    depth: depth,
                    isLeaf: item.isLeaf
                });

                // Add Children to Queue
                // NOTE: We construct the NEXT URL based on the click pattern if possible.
                // Since we can't "Click" and stay on this page (because we need to return the worker),
                // we must simulated the navigation.
                // Fortunately, AGCO CPQ updates URLs.
                // We will attempt to 'Click' in the browser to get the new URL,
                // BUT this blocks the worker.

                if (!item.isLeaf && depth < MAX_DEPTH) {
                    // Start a "Sub-Task" to get the link
                    // This is the tricky part of Parallel SPA scraping.
                    // We will queue a "Click Exploration" task.
                    // Simplified: We assume clicking an item *usually* appends an ID or Name to the URL.
                    // Since we can't guess the ID, we actually HAVE to click in this worker.

                    await clickAndEnqueue(page, item.title, depth, url);
                }
            }
        } else {
            // No cards = Leaf Page (Configuration)
            // console.log(`   [Worker ${id}] No cards. Leaf page.`);
        }

    } catch (err) {
        console.error(`   ❌ [Worker ${id}] Error: ${err.message}`);
    }

    return worker; // Return to pool
}

// --- HELPER: CLICK & CAPTURE LINKS ---
// Since we can't guess URLs, the worker must click the card, capture the new URL,
// add it to the global queue, and then GO BACK to process the next card.
async function clickAndEnqueue(page, titleToClick, currentDepth, currentUrl) {
    try {
        // Find specific card by text
        const cards = await page.$$('.brand-card-group, app-cpq-product-card, .card');
        let targetCard;

        for (const c of cards) {
            const txt = await page.evaluate(el => el.innerText + (el.querySelector('img')?.alt || ""), c);
            if (txt.includes(titleToClick)) {
                targetCard = c;
                break;
            }
        }

        if (targetCard) {
            // Click
            const clickTarget = await targetCard.$('img') || targetCard;
            await clickTarget.click();

            // Wait for URL change
            await new Promise(r => setTimeout(r, 2000)); // Wait for Angular routing
            const newUrl = page.url();

            if (newUrl !== currentUrl) {
                // Success! We found a new link. Add to Main Queue
                // console.log(`      + Queueing: ${newUrl}`);
                queue.push({ url: newUrl, depth: currentDepth + 1, parent: titleToClick });

                // Go back to process siblings
                await page.goBack();
                await waitForContent(page);
            }
        }
    } catch (e) {
        // Ignore click errors, move to next
    }
}

async function waitForContent(page) {
    try {
        await page.waitForFunction(() => !document.querySelector('.loader-container'), { timeout: 5000 });
    } catch(e) {}
    await new Promise(r => setTimeout(r, 1000));
}