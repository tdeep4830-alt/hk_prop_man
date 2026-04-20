import { Scale, BookOpen, Search } from "lucide-react";
import Link from "next/link";

const FEATURES = [
  {
    icon: Scale,
    title: "條文釋義",
    description:
      "深度解析《建築物管理條例》Cap. 344 各條文及大廈公契，以清晰的白話文解釋複雜法律概念，讓非法律專業的業主也能完全理解自身權利。",
    tags: ["Cap. 344", "大廈公契", "法團章程", "會議決議"],
  },
  {
    icon: BookOpen,
    title: "實務指南",
    description:
      "提供成立業主立案法團、大型維修工程招標、管理費追討、更換物業管理公司等完整的操作程序及注意事項，每步驟均有法律依據。",
    tags: ["成立法團", "維修招標", "管理費", "換管理公司"],
  },
  {
    icon: Search,
    title: "案例分析",
    description:
      "引用土地審裁處、區域法院及上訴法庭的真實判例，以實際裁決輔助法律論述。所有引用資料均標明案例編號，可自行追溯查閱原文。",
    tags: ["土地審裁處", "LDBM 判例", "裁決全文", "上訴案例"],
  },
] as const;

export function Features() {
  return (
    <section id="features" className="py-24 px-6 bg-zinc-50">
      <div className="max-w-5xl mx-auto">

        <div className="text-center mb-16">
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
            核心能力
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900 mb-4">
            三大專業領域
          </h2>
          <p className="text-zinc-500 text-base max-w-xl mx-auto leading-relaxed">
            覆蓋香港物業管理法律的全面知識體系，從基礎法規到複雜爭議，一一解答。
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: Icon, title, description, tags }) => (
            <article
              key={title}
              className="group bg-white border border-zinc-200 rounded-2xl p-7 flex flex-col
                         hover:border-zinc-400 hover:shadow-md transition-all duration-200"
            >
              <div className="w-11 h-11 bg-zinc-100 rounded-xl flex items-center justify-center mb-5
                              group-hover:bg-zinc-900 transition-colors duration-200 shrink-0">
                <Icon className="w-5 h-5 text-zinc-500 group-hover:text-white transition-colors duration-200" />
              </div>

              <h3 className="font-semibold text-zinc-900 text-lg mb-2.5">{title}</h3>

              <p className="text-sm text-zinc-500 leading-relaxed mb-5 flex-1">{description}</p>

              <div className="flex flex-wrap gap-1.5">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs bg-zinc-100 text-zinc-500 px-2.5 py-0.5 rounded-md font-medium"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>

        <div className="mt-14 text-center border border-zinc-200 rounded-2xl bg-white px-8 py-12">
          <h3 className="text-xl font-bold text-zinc-900 mb-2">立即體驗 AI 法律顧問</h3>
          <p className="text-zinc-500 text-sm mb-7 max-w-sm mx-auto">
            輸入您的問題，AI 將在數秒內引用法律條文及判例為您作答
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 bg-zinc-900 text-white
                       px-6 py-3 rounded-xl font-medium text-sm
                       hover:bg-zinc-700 transition-colors"
          >
            開始免費對話
          </Link>
        </div>
      </div>
    </section>
  );
}
