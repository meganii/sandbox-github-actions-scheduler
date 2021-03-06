const project = "villagepump";

const pagesResponse = await fetch(`https://scrapbox.io/api/pages/${project}/?limit=1`);
const pageNum = (await pagesResponse.json()).count;
const limitParam = 1000;
const maxIndex = Math.floor(pageNum / 1000) + 1;

const pages: any[] = [];
const promises = [...Array(maxIndex)]
.map(async (_, index) => {
    const json = await fetch(`https://scrapbox.io/api/pages/${project}/?limit=${limitParam}&skip=${index*1000}`)
    .then(res => res.json());
    pages.push(...json.pages);
});
await Promise.all(promises);
const titles = pages.map((page) => page.title);

const skip = 100;
const detailPages: Array<Object> = [];
// skip件づつfetchする
for (let i =0; i < titles.length; i += skip) {
  console.log(`[scrapbox-external-backup] Start fetching ${i} - ${i + skip} pages.`);
  // 一気にAPIを叩いてページ情報を取得する
  const promises = titles.slice(i, i+skip)
    .map(async (pageTitle: string, j: number) => {
      console.log(`[page ${i + j}@scrapbox-external-backup] start fetching "/${project}/${pageTitle}"`);
      const res = await fetch(`https://scrapbox.io/api/pages/${project}/${encodeURIComponent(pageTitle)}`);
      console.log(`[page ${i + j}@scrapbox-external-backup] finish fetching "/${project}/${pageTitle}"`);
      const {id, title, created, updated, lines} = await res.json();
      detailPages.push({id, title, created, updated, lines});
    });
  await Promise.all(promises);
  console.log(`Finish fetching ${i} - ${i + skip} pages.`);
}

console.log(writeJson("./data.json", detailPages));

function writeJson(path: string, data: object): string {
    try {
      Deno.writeTextFileSync(path, JSON.stringify(data));
  
      return "Written to " + path;
    } catch (e) {
      return e.message;
    }
  }
  