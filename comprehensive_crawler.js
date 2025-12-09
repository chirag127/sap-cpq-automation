const puppeteer = require('puppeteer');
const fs = require('fs');

// --- CONFIGURATION ---
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator';
const OUTPUT_FILE = 'agco_full_dump.json';
const MAX_DEPTH = 6;

// --- STATE ---
let fullData = [];
let visitedUrls = new Set();

// ==========================================
// 1. GLOBAL HELPERS
// ==========================================

async function waitForAngular(page) {
    try {
        await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 });
    } catch (e) {}
    // Hard pause for Angular data binding
    await new Promise(r => setTimeout(r, 3000));
}

async function handleCookies(page) {
    try {
        const btnSelector = '#truste-consent-button';
        const btn = await page.$(btnSelector);
        if (btn) {
            console.log('🍪 Smashing Cookie Banner...');
            await btn.click();
            await new Promise(r => setTimeout(r, 2000));
        }
    } catch (e) {}
}

// ==========================================
// 2. MAIN LOGIC
// ==========================================

async function scrape() {
    console.log("🤖 Launching Scraper V5 (Aggressive Wait)...");

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();
    page.setDefaultNavigationTimeout(0);

    try {
        console.log(`🚀 Navigating to Home...`);
        await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });

        await waitForAngular(page);
        await handleCookies(page);

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
 * Recursive Scraper
 */
async function scrapeLevel(page, parentName, depth) {
    const currentUrl = page.url();

    if (depth >= MAX_DEPTH) {
        console.log(`   🛑 Max depth reached.`);
        return;
    }

    // Cycle check
    const stateKey = `${currentUrl}::${depth}`;
    if (visitedUrls.has(stateKey)) return;
    visitedUrls.add(stateKey);

    console.log(`\n📂 [Level ${depth}] Scanning: "${parentName}"`);

    // --- SMART SELECTOR DETECTION ---
    let validSelector = '';

    // Strategy: explicit wait for known types based on depth
    try {
        if (depth === 0) {
            // Home Page always has brand-card-group
            await page.waitForSelector('.brand-card-group', { timeout: 10000 });
            validSelector = '.brand-card-group';
        } else {
            // Inner pages usually have product cards
            // We wait up to 15s for ANY card to appear
            console.log("   (Waiting for cards to paint...)");
            await page.waitForFunction(() =>
                document.querySelector('app-cpq-product-card') ||
                document.querySelector('.product-item') ||
                document.querySelector('.card'),
                { timeout: 15000 }
            );

            // Determine which one appeared
            if (await page.$('app-cpq-product-card')) validSelector = 'app-cpq-product-card';
            else if (await page.$('.product-item')) validSelector = '.product-item';
            else validSelector = '.card';
        }
    } catch (e) {
        console.log(`   ⚠️ Timeout waiting for cards at ${parentName}.`);
    }

    if (!validSelector) {
        console.log("   📝 No cards found. Taking screenshot...");
        await page.screenshot({ path: `fail_${parentName.replace(/[^a-z0-9]/gi, '_')}.png` });
        return;
    }

    // --- COLLECT ITEMS ---
    const cards = await page.$$(validSelector);
    console.log(`   Found ${cards.length} items using "${validSelector}"`);

    for (let i = 0; i < cards.length; i++) {
        // Refresh DOM
        if (i > 0) await waitForAngular(page);

        const freshCards = await page.$$(validSelector);
        const card = freshCards[i];
        if (!card) continue;

        // Extract Data
        let data = await page.evaluate((el) => {
            const tEl = el.querySelector('.card-title') || el.querySelector('h4') || el.querySelector('h3');
            const dEl = el.querySelector('.card-text');
            const imgEl = el.querySelector('img');

            let title = tEl ? tEl.innerText.trim() : "";
            if (!title && imgEl) title = imgEl.getAttribute('alt'); // Home page brands

            return {
                title: title || "Unknown",
                desc: dEl ? dEl.innerText.trim() : "",
                img: imgEl ? imgEl.src : ""
            };
        }, card);

        console.log(`   👉 [${i+1}/${cards.length}] Processing: ${data.title}`);

        fullData.push({ level: depth, parent: parentName, ...data });

        // --- CHECKBOX CHECK (Leaf Node) ---
        // Your model HTML has <div class="chk chk-round">
        const isLeaf = await card.$('.chk, input[type="checkbox"]');

        if (!isLeaf) {
            try {
                // Click
                const clickTarget = await card.$('img') || card;
                await clickTarget.click();

                // Wait for URL change or DOM update
                await waitForAngular(page);

                // Check URL
                if (page.url() === currentUrl) {
                    console.log("      (URL didn't change. Skipping recursion.)");
                } else {
                    // RECURSE
                    await scrapeLevel(page, data.title, depth + 1);

                    // BACK
                    console.log("      ⬅️ Back...");
                    await page.goBack();
                    await waitForAngular(page);
                }
            } catch (err) {
                console.log(`      ⚠️ Navigation failed: ${err.message}`);
            }
        } else {
            console.log("      (Leaf Node - Checkbox detected)");
        }
    }
}

scrape();