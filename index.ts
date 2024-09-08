import { readableStreamFromIterable } from "https://deno.land/std@0.166.0/streams/mod.ts";
import { JsonStringifyStream } from "https://deno.land/std@0.166.0/encoding/json/stream.ts";
import { delay } from "https://deno.land/std/async/mod.ts";

interface TitlePage {
  id: string,
  title: string,
  created: number,
  updated: number
}

const project = "villagepump";
const dist_stats = `./${project}/stats/pages.json`;
const dist_data = "./data.json";

const pagesResponse = await fetch(`https://scrapbox.io/api/pages/${project}/?limit=1`);
const pageNum = (await pagesResponse.json()).count;
const limitParam = 1000;
const maxIndex = Math.floor(pageNum / 1000) + 1;

// リクエストを送信する関数
async function fetchWithRetry(url: string, retryCount = 3, delayMs = 1000): Promise<any> {
  for (let i = 0; i < retryCount; i++) {
    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        throw new Error(`Expected JSON, got ${contentType}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`Attempt ${i + 1} failed:`, error);
      if (i < retryCount - 1) {
        console.log(`Retrying in ${delayMs}ms...`);
        await delay(delayMs);
      } else {
        throw error;
      }
    }
  }
  throw new Error("Max retry count reached");
}

// メイン処理
async function fetchAllPages(project: string, limitParam: number, maxIndex: number): Promise<any[]> {
  const pages: any[] = [];
  for (let index = 0; index < maxIndex; index++) {
    try {
      console.log(`Fetching data for index ${index}...`);
      const json = await fetchWithRetry(`https://scrapbox.io/api/pages/${project}/?limit=${limitParam}&skip=${index * 1000}`);
      pages.push(...json.pages);
      
      // 各リクエスト後に遅延を追加
      if (index < maxIndex - 1) {
        console.log("Waiting before next request...");
        await delay(2000); // 2秒の遅延を追加
      }
    } catch (error) {
      console.error(`Error fetching data for index ${index}:`, error);
    }
  }
  return pages;
}

const pages = await fetchAllPages(project, limitParam, maxIndex);
const titles = pages.map((page) => {
  return {
    "id": page.id,
    "title": page.title,
    "created": page.created,
    "updated": page.updated,
    "image": page.image,
    "descriptions": page.descriptions,
  } as TitlePage;
});
titles.sort((a: TitlePage, b: TitlePage): number => {
  return a.created - b.created;
});

writeJson(dist_stats, {
  projectName: project,
  count: pageNum,
  pages: titles
})

const skip = 100;
const detailPages: Array<Object> = [];
// skip件づつfetchする
for (let i = 0; i < titles.length; i += skip) {
  console.log(`[scrapbox-external-backup] Start fetching ${i} - ${i + skip} pages.`);
  // 一気にAPIを叩いてページ情報を取得する
  const promises = titles.slice(i, i + skip)
    .map(async (pageTitle: TitlePage, j: number) => {
      console.log(`[page ${i + j}@scrapbox-external-backup] start fetching "/${project}/${pageTitle.title}"`);
      const res = await fetch(`https://scrapbox.io/api/pages/${project}/${encodeURIComponent(pageTitle.title)}`);
      console.log(`[page ${i + j}@scrapbox-external-backup] finish fetching "/${project}/${pageTitle.title}"`);
      const { id, title, created, updated, lines } = await res.json();
      detailPages.push({ id, title, created, updated, lines });
    });
  await Promise.all(promises);
  console.log(`Finish fetching ${i} - ${i + skip} pages.`);
}

// JSON Lines形式でpagesを出力 - 出力処理後JSON形式に変換が必要
const file = await Deno.open(dist_data, { create: true, write: true });
readableStreamFromIterable(detailPages)
  .pipeThrough(new JsonStringifyStream({ suffix: ",\n" })) // convert to JSON Text Sequences
  .pipeThrough(new TextEncoderStream()) // convert a string to a Uint8Array
  .pipeTo(file.writable)
  .then(() => console.log("write success"));

function writeJson(path: string, data: object): string {
  try {
    Deno.writeTextFileSync(path, JSON.stringify(data));

    return "Written to " + path;
  } catch (e) {
    return e.message;
  }
}
