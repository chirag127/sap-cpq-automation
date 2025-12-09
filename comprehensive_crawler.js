const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_full_dump.json';
const MAX_DEPTH = 6;

// --- STATE MANAGEMENT ---
let fullData = [];
let visitedUrls = new Set();

// --- GLOBAL HELPER FUNCTIONS ---

// 1. Robust Wait for Angular/SPA Loading
async function waitForAngular(page) {
    try {
        // Wait for spinner to disappear
        await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 });
    } catch (e) {
        // If timeout, just continue (spinner might not have appeared)
    }
    // Hard wait for grid repaint
    await new Promise(r => setTimeout(r, 2000));
}

// 2. Kill Cookie Banners
async function handleCookies(page) {
    try {
        const btn = await page.$('#truste-consent-button');
        if (btn) {
            console.log('🍪 Clicking Cookie Banner...');
            await btn.click();
            await waitForAngular(page);
        }
    } catch (e) {}
}

// --- MAIN SCRAPER ---

async function scrape() {
    console.log("🤖 Launching Scraper V4 (Fixed Scope)...");

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();
    page.setDefaultNavigationTimeout(60000);

    try {
        console.log(`🚀 Navigating to Home: ${BASE_URL}`);
        await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });

        await waitForAngular(page);
        await handleCookies(page);

        // Start recursion
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
 * Recursive Scraper Function
 */
async function scrapeLevel(page, parentName, depth) {
    const currentUrl = page.url();

    if (depth >= MAX_DEPTH) {
        console.log(`   🛑 Max depth reached.`);
        return;
    }

    // Deduplication logic
    const stateKey = `${currentUrl}::${depth}`;
    if (visitedUrls.has(stateKey)) return;
    visitedUrls.add(stateKey);

    console.log(`\n📂 [Level ${depth}] Scanning: "${parentName}"`);

    // --- SELECTOR STRATEGY ---
    const possibleSelectors = [
        '.brand-card-group',        // Home Page
        'app-cpq-product-card',     // Product Cards
        '.product-item',            // Generic List
        '.category-tile',           // Category Tiles
        '.card'                     // Fallback
    ];

    let validSelector = '';
    for (const sel of possibleSelectors) {
        if (await page.$(sel)) {
            validSelector = sel;
            break;
        }
    }

    if (!validSelector) {
        console.log("   📝 No known cards found. Probably a Leaf/Config page.");
        return;
    }

    // --- COLLECT ITEMS ---
    const cards = await page.$$(validSelector);
    console.log(`   Found ${cards.length} items using selector: "${validSelector}"`);

    // --- LOOP ITEMS ---
    for (let i = 0; i < cards.length; i++) {
        // Refresh DOM context
        await waitForAngular(page);
        let freshCards = await page.$$(validSelector);
        let card = freshCards[i];
        if (!card) continue;

        // Extract Data
        let data = await page.evaluate((el) => {
            // Try different title locations
            const tEl = el.querySelector('.card-title') || el.querySelector('h4') || el.querySelector('h3');
            const imgEl = el.querySelector('img');

            let title = tEl ? tEl.innerText.trim() : "";
            // Fallback to Alt text if no visible title (common on Home Page)
            if (!title && imgEl) title = imgEl.getAttribute('alt');

            return { title: title || "Unknown Item" };
        }, card);

        console.log(`   👉 [${i+1}/${cards.length}] Processing: ${data.title}`);

        // Add to global data
        fullData.push({ level: depth, parent: parentName, ...data });

        // --- CLICK & RECURSE ---
        const isLeaf = await card.$('input[type="checkbox"]');

        if (!isLeaf) {
            try {
                // Determine click target (Image works best for brands, Card body for others)
                const clickable = await card.$('img') || card;

                await clickable.click();

                // Wait for navigation
                try {
                    await page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 8000 });
                } catch(e) {
                    await waitForAngular(page); // Fallback wait
                }

                // RECURSE
                await scrapeLevel(page, data.title, depth + 1);

                // GO BACK
                console.log("      ⬅️ Back...");
                await page.goBack({ waitUntil: 'domcontentloaded' });
                await waitForAngular(page);

            } catch (err) {
                console.log(`      ⚠️ Click interaction failed: ${err.message}`);
            }
        } else {
            console.log("      (Leaf Node Detected - Skipping click)");
        }
    }
}

scrape();