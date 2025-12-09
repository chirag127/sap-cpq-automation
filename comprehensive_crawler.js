const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_full_dump.json';
const MAX_DEPTH = 6; // Hard stop to prevent infinite loops

// --- STATE MANAGEMENT ---
let fullData = [];
let visitedUrls = new Set(); // Tracks visited pages to prevent cycles

async function scrape() {
    console.log("🤖 Launching Smart Scraper V2...");

    const browser = await puppeteer.launch({
        headless: false, // Keep false to monitor progress
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();

    // 1. HELPER: Wait for SPA to settle
    const waitForAngular = async () => {
        try {
            await page.waitForSelector('.loader-container', { hidden: true, timeout: 4000 });
        } catch (e) { /* Loader didn't appear or stuck, moving on */ }
        await new Promise(r => setTimeout(r, 800)); // Small debounce for stability
    };

    // 2. HELPER: Kill Cookie Banner
    const handleCookies = async () => {
        try {
            const btn = await page.$('#truste-consent-button');
            if (btn) {
                console.log('🍪 Smashing Cookie Banner...');
                await btn.click();
                await waitForAngular();
            }
        } catch (e) {}
    };

    try {
        console.log(`🚀 Navigating to Home: ${BASE_URL}`);
        await page.goto(BASE_URL, { waitUntil: 'networkidle2' });
        await waitForAngular();
        await handleCookies();

        // Start Scraping
        await scrapeLevel(page, 'Home', 0);

    } catch (err) {
        console.error("❌ CRITICAL ERROR:", err);
    } finally {
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(fullData, null, 2));
        console.log(`\n✅ DONE! Saved ${fullData.length} items to ${OUTPUT_FILE}`);
        await browser.close();
    }
}

/**
 * Recursive Scraper with Loop Protection
 */
async function scrapeLevel(page, parentName, depth) {
    const currentUrl = page.url();

    // --- STOP CONDITIONS ---
    if (depth >= MAX_DEPTH) {
        console.log(`   🛑 Max depth (${MAX_DEPTH}) reached. Stopping recursion.`);
        return;
    }

    // Cycle Detection: If we've scraped this exact URL at this depth before, stop.
    // (We include depth in key because sometimes you go back to Home)
    const stateKey = `${currentUrl}::${depth}`;
    if (visitedUrls.has(stateKey)) {
        console.log(`   🔄 Cycle detected at ${parentName}. Skipping.`);
        return;
    }
    visitedUrls.add(stateKey);

    console.log(`\n📂 [Level ${depth}] Scanning: "${parentName}"`);

    // --- IDENTIFY CARDS ---
    let cardSelector = '';
    if (await page.$('.brand-card-group')) {
        cardSelector = '.brand-card-group'; // Home Page
    } else if (await page.$('app-cpq-product-card')) {
        cardSelector = 'app-cpq-product-card'; // Inner Pages
    } else {
        console.log("   📝 No standard cards found. Likely a Leaf Page (Config).");
        return;
    }

    // --- COLLECT ITEMS ---
    const cards = await page.$$(cardSelector);
    console.log(`   Found ${cards.length} items.`);

    // If 0 items, stop
    if (cards.length === 0) return;

    // --- PROCESS ITEMS LOOP ---
    for (let i = 0; i < cards.length; i++) {
        // Refresh DOM elements (SPA Refresh)
        let freshCards = await page.$$(cardSelector);
        let card = freshCards[i];
        if (!card) continue;

        // Extract Data
        let data = await page.evaluate((el, sel) => {
            let title = "Unknown";
            let desc = "";
            let img = "";

            if (sel.includes('brand')) {
                const imgEl = el.querySelector('img');
                title = imgEl ? imgEl.alt : "Brand";
                img = imgEl ? imgEl.src : "";
            } else {
                const tEl = el.querySelector('.card-title');
                const dEl = el.querySelector('.card-text');
                const iEl = el.querySelector('img');
                if (tEl) title = tEl.innerText.trim();
                if (dEl) desc = dEl.innerText.trim();
                if (iEl) img = iEl.src;
            }
            return { title, desc, img };
        }, card, cardSelector);

        // Filter out empty garbage
        if (!data.title) continue;

        console.log(`   👉 [${i+1}/${cards.length}] Item: ${data.title}`);

        // SAVE DATA
        fullData.push({
            level: depth,
            parent: parentName,
            ...data,
            url: page.url()
        });

        // --- RECURSION LOGIC ---
        // We only click if it's NOT a leaf node (Model).
        // Models usually have checkboxes. Categories don't.
        const hasCheckbox = await card.$('input[type="checkbox"]');

        if (!hasCheckbox) {
            try {
                // Pre-click URL check
                const urlBefore = page.url();

                // CLICK
                const clickTarget = (cardSelector.includes('brand')) ? await card.$('img') : card;
                if (clickTarget) {
                    await clickTarget.click();

                    // Wait for Loading
                    try {
                        await page.waitForSelector('.loader-container', { hidden: true, timeout: 3000 });
                    } catch(e){}

                    // Post-click URL check
                    const urlAfter = page.url();

                    // SMART CHECK: Did we actually move?
                    // If URL is same, and we are deep (Level 3+), it's likely a leaf node
                    // or a "Filter" update, not a new page.
                    if (urlBefore === urlAfter && depth > 2) {
                        console.log("      (URL didn't change. Treating as leaf node.)");
                    } else {
                        // Recurse deeper
                        await scrapeLevel(page, data.title, depth + 1);

                        // GO BACK
                        console.log("      ⬅️ Going Back...");
                        await page.goBack({ waitUntil: 'networkidle2' });
                        try {
                            await page.waitForSelector('.loader-container', { hidden: true, timeout: 3000 });
                        } catch(e){}
                    }
                }
            } catch (err) {
                console.log(`      ⚠️ Error clicking ${data.title}: ${err.message}`);
            }
        } else {
            console.log("      (Checkbox detected. This is a Model. Saved & Skipped drill-down.)");
        }
    }
}

scrape();