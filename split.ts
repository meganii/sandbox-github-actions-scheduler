const filepath = "./data.json";
const distpath = "./villagepump/pages/";

const text = Deno.readTextFileSync(filepath);
const pages = JSON.parse(text);

for (const page of pages) {
    Deno.writeTextFile(distpath + page.id + '.json', JSON.stringify(page, null, 2));
}