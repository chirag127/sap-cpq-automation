const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_full_dump.json';
const MAX_DEPTH = 6;

// --- STATE MANAGEMENT ---
let fullData = [];
let visitedUrls = new Set();

async function scrape() {
    console.log("🤖 Launching Scraper V3 (Broad Selectors)...");

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();
    // Increase default timeout to 60s for slow assets
    page.setDefaultNavigationTimeout(60000);

    // 1. HELPER: Robust Wait
    const waitForAngular = async () => {
        try {
            // Wait for spinner to disappear
            await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 });
        } catch (e) {}
        // Hard wait for grid to paint
        await new Promise(r => setTimeout(r, 2000));
    };

    // 2. HELPER: Kill Cookies
    const handleCookies = async () => {
        try {
            const btn = await page.$('#truste-consent-button');
            if (btn) {
                console.log('🍪 Clicking Cookie Banner...');
                await btn.click();
                await waitForAngular();
            }
        } catch (e) {}
    };

    try {
        console.log(`🚀 Navigating to Home...`);
        await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
        await waitForAngular();
        await handleCookies();

        await scrapeLevel(page, 'Home', 0);

    } catch (err) {
        console.error("❌ CRITICAL ERROR:", err);
    } finally {
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(fullData, null, 2));
        console.log(`\n✅ DONE! Saved ${fullData.length} items.`);
        await browser.close();
    }
}

/**
 * Recursive Scraper
 */
async function scrapeLevel(page, parentName, depth) {
    const currentUrl = page.url();

    if (depth >= MAX_DEPTH) {
        console.log(`   🛑 Max depth reached.`);
        return;
    }

    const stateKey = `${currentUrl}::${depth}`;
    if (visitedUrls.has(stateKey)) return;
    visitedUrls.add(stateKey);

    console.log(`\n📂 [Level ${depth}] Scanning: "${parentName}"`);

    // --- BROAD SELECTOR STRATEGY ---
    // We try multiple selectors to find *anything* clickable
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
        console.log("   📝 No known cards found. Taking debug screenshot...");
        await page.screenshot({ path: `debug_level_${depth}_${parentName}.png` });
        return;
    }

    // --- COLLECT ITEMS ---
    const cards = await page.$$(validSelector);
    console.log(`   Found ${cards.length} items using selector: "${validSelector}"`);

    // --- LOOP ITEMS ---
    for (let i = 0; i < cards.length; i++) {
        // Refresh DOM
        await waitForAngular();
        let freshCards = await page.$$(validSelector);
        let card = freshCards[i];
        if (!card) continue;

        // Extract Data
        let data = await page.evaluate((el) => {
            // Try to find text in standard places
            const tEl = el.querySelector('.card-title') || el.querySelector('h4') || el.querySelector('h3');
            const imgEl = el.querySelector('img');

            let title = tEl ? tEl.innerText.trim() : "";
            // Fallback: Use Image Alt text if no title (Home page brands)
            if (!title && imgEl) title = imgEl.alt;

            return { title: title || "Unknown Item" };
        }, card);

        console.log(`   👉 [${i+1}/${cards.length}] Processing: ${data.title}`);

        // Add to data
        fullData.push({ level: depth, parent: parentName, ...data });

        // --- CLICK & RECURSE ---
        // Check for checkbox (Leaf node indicator)
        const isLeaf = await card.$('input[type="checkbox"]');

        if (!isLeaf) {
            try {
                // Click Logic
                const clickable = await card.$('img') || card; // Click image if present, else card
                await clickable.click();

                // Wait for navigation
                try {
                    await page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 10000 });
                } catch(e) {
                    await waitForAngular(); // Just wait for Angular if no nav event
                }

                // Recurse
                await scrapeLevel(page, data.title, depth + 1);

                // Go Back
                console.log("      ⬅️ Back...");
                await page.goBack({ waitUntil: 'domcontentloaded' });
                await waitForAngular();

            } catch (err) {
                console.log(`      ⚠️ Click failed: ${err.message}`);
            }
        } else {
            console.log("      (Leaf Node Detected - Skipping click)");
        }
    }
}

scrape();