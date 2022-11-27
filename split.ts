const filepath = "./data.json";
const distpath = "./villagepump/pages/";

const text = Deno.readTextFileSync(filepath);
const pages = JSON.parse(text);

const replaceFilename = (filename : string) : string => {
    let str = filename;
    str = str.replaceAll("/", "%2F");
    str = str.replaceAll('\\', "%5");
    str = str.replaceAll("\"", "%22");
    str = str.replaceAll("\t", " ");
    str = str.replaceAll("?", "？");
    str = str.replaceAll(":", "：");
    str = str.replaceAll("|", "｜");
    str = str.replaceAll("<", "＜");
    str = str.replaceAll(">", "＞");
    str = str.replaceAll("*", "＊");
    return str;
};

for (const page of pages) {
    const filename = replaceFilename(page.title);
    Deno.writeTextFile(distpath + filename + '.json', JSON.stringify(page, null, 2));
}