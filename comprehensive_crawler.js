const puppeteer = require('puppeteer');
const fs = require('fs');

// Configuration
const BASE_URL = 'https://cpq.agcocorp.com/agco/customer/en_GB/configurator'; // Derived from your HTML <base> tag
const OUTPUT_FILE = 'agco_data.json';

// Global variable to store scraped data
let fullData = [];

async function scrape() {
    // Launch browser (Headless: false allows you to see it working, set to true for production)
    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();

    // Helper: Wait for Angular animations/loaders to finish
    const waitForAngular = async () => {
        try {
            // Your HTML shows a loader container
            await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 });
        } catch (e) {
            // Ignore timeout if loader doesn't appear
        }
        // Wait a bit for DOM to settle
        await new Promise(r => setTimeout(r, 1000));
    };

    // Helper: Handle Cookie Popup
    const handleCookies = async () => {
        try {
            const cookieBtnSelector = '#truste-consent-button';
            // Check if button exists based on your provided HTML
            if (await page.$(cookieBtnSelector) !== null) {
                console.log('🍪 Cookie popup detected. Clicking "Accept All"...');
                await page.click(cookieBtnSelector);
                await waitForAngular();
            }
        } catch (e) {
            console.log('No cookie popup found or already closed.');
        }
    };

    try {
        console.log(`🚀 Navigating to ${BASE_URL}...`);
        await page.goto(BASE_URL, { waitUntil: 'networkidle2' });

        await waitForAngular();
        await handleCookies();

        // Start the recursive scraping process
        // We start at depth 0 (Brands)
        await scrapeLevel(page, 'Home', 0);

    } catch (error) {
        console.error('❌ General Error:', error);
    } finally {
        // Save Data
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(fullData, null, 2));
        console.log(`\n✅ Scraping complete. Data saved to ${OUTPUT_FILE}`);
        await browser.close();
    }
}

/**
 * Recursive function to handle the hierarchy:
 * Brand -> Product Group -> Sub Group -> Series -> Models
 */
async function scrapeLevel(page, parentName, depth) {
    console.log(`\n📂 Scraping Level ${depth} under "${parentName}"`);

    // 1. Identify what kind of cards are on the page
    // Your HTML uses different wrappers but similar card structures
    // .brand-card-group (Home) OR app-cpq-product-card (Inner pages)
    let cardSelector = '';

    // Check for Brand Cards (Home Page)
    const brandsExist = await page.$('.brand-card-group');
    // Check for Product/Series Cards
    const productsExist = await page.$('app-cpq-product-card');

    if (brandsExist) {
        cardSelector = '.brand-card-group';
    } else if (productsExist) {
        cardSelector = 'app-cpq-product-card';
    } else {
        console.log('   Create Leaf Node found (Specific Model config). Stopping recursion here.');
        return;
    }

    // 2. Get Count of items
    const cards = await page.$$(cardSelector);
    console.log(`   Found ${cards.length} items to process.`);

    // 3. Loop through items
    // NOTE: In SPAs, DOM elements become stale after navigation.
    // We must scrape data, save it, then re-query the DOM or click by index.

    for (let i = 0; i < cards.length; i++) {
        // Re-query elements because DOM refreshes on back navigation
        await new Promise(r => setTimeout(r, 1000)); // Stability pause
        let currentCards = await page.$$(cardSelector);
        let card = currentCards[i];

        if (!card) continue;

        // Extract Data
        let itemData = await page.evaluate((el, type) => {
            let title = '';
            let description = '';
            let image = '';

            if (type === '.brand-card-group') {
                // Logic for Brand Page HTML
                const imgEl = el.querySelector('img.card-img');
                title = imgEl ? imgEl.getAttribute('alt') : 'Unknown Brand';
                image = imgEl ? imgEl.src : '';
                description = 'Brand Category';
            } else {
                // Logic for Product/Series Page HTML
                const titleEl = el.querySelector('.card-title');
                const textEl = el.querySelector('.card-text');
                const imgEl = el.querySelector('img');

                title = titleEl ? titleEl.innerText.trim() : 'Unknown Product';
                description = textEl ? textEl.innerText.trim() : '';
                image = imgEl ? imgEl.src : '';
            }

            return { title, description, image };
        }, card, cardSelector);

        console.log(`   👉 Processing: ${itemData.title}`);

        // Add to global data
        fullData.push({
            parent: parentName,
            depth: depth,
            ...itemData
        });

        // 4. Click and Recurse (Drill down)
        // We only drill down if it's NOT a leaf node (Model selection with checkboxes)
        const isLeaf = await card.$('input[type="checkbox"]'); // Your model HTML has checkboxes

        if (!isLeaf) {
            try {
                // Click the card (or the image inside it if it's a brand card)
                if (cardSelector === '.brand-card-group') {
                    const clickTarget = await card.$('img.card-img');
                    if (clickTarget) await clickTarget.click();
                } else {
                    await card.click();
                }

                // Wait for navigation/loading
                try {
                    await page.waitForNavigation({ timeout: 5000, waitUntil: 'networkidle2' });
                } catch (e) {
                    // SPAs sometimes don't trigger standard navigation events, just wait for loader
                    await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 }).catch(()=>{});
                }

                // RECURSIVE CALL
                await scrapeLevel(page, itemData.title, depth + 1);

                // GO BACK UP THE TREE
                console.log('   ⬅️ Going back...');
                await page.goBack({ waitUntil: 'networkidle0' });
                await page.waitForSelector('.loader-container', { hidden: true, timeout: 5000 }).catch(()=>{});

            } catch (err) {
                console.error(`   Error clicking ${itemData.title}:`, err.message);
            }
        } else {
            console.log('   🛑 End of line (Model configuration).');
        }
    }
}

// Run the script
scrape();