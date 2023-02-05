const filepath = "./data.json";
const distpath = "./villagepump/pages/";

const text = Deno.readTextFileSync(filepath);
const content = JSON.parse(text);

for (const page of content['pages']) {
    Deno.writeTextFile(distpath + page.id + '.json', JSON.stringify(page, null, 2));
}