import type { Metadata } from "next";
import Link from "next/link";
import { PageFooter } from "@/components/PageFooter/PageFooter";

// 정책 버전·최종 업데이트. 문서 개정 시 이 두 값만 갱신한다.
const POLICY_VERSION = "v0.1 (데모)";
const LAST_UPDATED = "2026-08-24";

export const metadata: Metadata = {
  title: "AI 이용 안내 | 바름",
  description:
    "바름이 어떤 AI를 어떻게 사용하는지, 무엇을 하고 무엇을 하지 않는지, 결과의 한계와 사람의 최종 검토 책임을 안내합니다.",
};

/** 문서 섹션 한 덩어리. 번호가 붙은 제목(h2)과 본문을 감싼다. */
function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mt-[38px] scroll-mt-[24px]">
      <h2 className="m-0 mb-[14px] text-[var(--ink)] text-[19px] font-bold tracking-[-0.3px] break-keep">
        {title}
      </h2>
      <div className="text-[var(--ink-2)] text-[14.5px] leading-[1.8] break-keep space-y-[12px]">
        {children}
      </div>
    </section>
  );
}

export default function AiPolicyPage() {
  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 w-full max-w-[820px] mx-auto px-[24px] py-[44px] max-[640px]:px-[18px] max-[640px]:py-[30px]">
        {/* 데모 단계 고지 배너: 상태색이 아니라 중립 표면+테두리로. 경보가 아니라 안내다 */}
        <div className="flex items-start gap-[10px] border border-[var(--line-2)] bg-[var(--surface-sub)] p-[13px_16px] text-[13px] leading-[1.7] text-[var(--ink-2)] break-keep">
          <span aria-hidden="true" className="font-mono text-[var(--ink-3)] font-bold shrink-0 pt-[1px]">ⓘ</span>
          <span>
            본 문서는 <b className="text-[var(--ink)] font-semibold">데모 단계의 안내</b>이며, 실제 서비스 시행 전
            법률·개인정보 전문가의 검토가 필요합니다. 바름의 검사·생성 결과는 참고 정보이며 법적 자문이 아닙니다.
          </span>
        </div>

        {/* 제목 + 버전/일자 */}
        <div className="mt-[30px]">
          <div className="text-[var(--brand-ink)] mb-[10px] font-mono text-[11.5px] font-bold tracking-[0.4px]">
            AI 이용 안내
          </div>
          <h1 className="m-0 text-[var(--ink)] text-[32px] font-extrabold leading-[1.25] tracking-[-1px] break-keep">
            바름은 AI를 이렇게 씁니다
          </h1>
          <div className="mt-[12px] flex flex-wrap items-center gap-x-[14px] gap-y-[4px] text-[var(--ink-3)] font-mono text-[11.5px]">
            <span>버전 {POLICY_VERSION}</span>
            <span aria-hidden="true">·</span>
            <span>최종 업데이트 {LAST_UPDATED}</span>
          </div>
        </div>

        <Section id="uses-ai" title="1. 바름은 AI를 사용합니다">
          <p>
            바름은 화장품 광고의 위반 위험을 점검하고 대체 문구·상세페이지 초안을 만드는 과정에서
            생성형 AI(대규모 언어·이미지 모델)를 사용합니다. 이 안내는 바름이 AI를 어디에 쓰고,
            그 결과를 어떻게 받아들여야 하는지를 투명하게 밝히기 위한 문서입니다.
          </p>
        </Section>

        <Section id="ai-does" title="2. AI가 하는 작업">
          <ul className="list-disc pl-[20px] space-y-[8px] marker:text-[var(--ink-3)]">
            <li>업로드한 이미지에서 광고 문구를 <b className="text-[var(--ink)] font-semibold">텍스트로 추출</b>합니다(OCR).</li>
            <li>추출·입력된 문구가 화장품법상 <b className="text-[var(--ink)] font-semibold">위반 위험이 있는지 판정</b>하고, 근거가 되는 조항·기준을 제시합니다.</li>
            <li>위험 문구에 대한 <b className="text-[var(--ink)] font-semibold">대체 문구</b>와 상세페이지 문구 초안을 제안합니다.</li>
            <li>상세페이지 <b className="text-[var(--ink)] font-semibold">배경 이미지</b>를 생성합니다.</li>
          </ul>
        </Section>

        <Section id="ai-does-not" title="3. AI가 하지 않는 작업">
          <p>바름의 AI는 다음을 대신하지 않습니다.</p>
          <ul className="list-disc pl-[20px] space-y-[8px] marker:text-[var(--ink-3)]">
            <li><b className="text-[var(--ink)] font-semibold">법률 자문</b>을 제공하지 않습니다. 바름의 판정은 변호사·전문가의 법률 의견을 대체하지 않습니다.</li>
            <li>게시해도 되는지에 대한 <b className="text-[var(--ink)] font-semibold">최종 적합성 판단</b>을 내리지 않습니다. &quot;통과&quot;가 100% 안전을 보장하지 않습니다.</li>
            <li>규제 기관의 심의·승인을 대신하거나, 위반이 없음을 <b className="text-[var(--ink)] font-semibold">보증</b>하지 않습니다.</li>
          </ul>
        </Section>

        <Section id="models" title="4. 사용하는 모델과 외부 AI 서비스">
          <p>바름은 작업별로 아래 외부 AI 서비스를 사용합니다.</p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px] leading-[1.6]">
              <thead>
                <tr className="border-b border-[var(--line-2)] text-left text-[var(--ink-3)] font-mono text-[11.5px]">
                  <th className="py-[8px] pr-[12px] font-semibold">작업</th>
                  <th className="py-[8px] font-semibold">사용 AI</th>
                </tr>
              </thead>
              <tbody className="text-[var(--ink-2)]">
                <tr className="border-b border-[var(--line)]">
                  <td className="py-[10px] pr-[12px] align-top">이미지 텍스트 추출(OCR)</td>
                  <td className="py-[10px] align-top font-semibold text-[var(--ink)]">Google Gemini</td>
                </tr>
                <tr className="border-b border-[var(--line)]">
                  <td className="py-[10px] pr-[12px] align-top">광고 위반 판정</td>
                  <td className="py-[10px] align-top font-semibold text-[var(--ink)]">OpenAI (gpt-5-mini)</td>
                </tr>
                <tr className="border-b border-[var(--line)]">
                  <td className="py-[10px] pr-[12px] align-top">대체 문구·상세페이지 문구 생성</td>
                  <td className="py-[10px] align-top font-semibold text-[var(--ink)]">Google Gemini</td>
                </tr>
                <tr>
                  <td className="py-[10px] pr-[12px] align-top">배경 이미지 생성</td>
                  <td className="py-[10px] align-top font-semibold text-[var(--ink)]">Google Gemini (이미지 생성 모델)</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-[var(--ink-3)] text-[13px]">
            구체적인 모델 버전은 서비스 개선에 따라 바뀔 수 있습니다.
            관측·디버깅을 위해 LangSmith 트레이싱을 사용할 수 있으며, 이 경우 AI 호출의 일부 입력·출력이 전송됩니다.
          </p>
        </Section>

        <Section id="input-data" title="5. 입력 데이터와 개인정보 처리">
          <p>
            위 작업을 위해 이용자가 업로드한 이미지와 추출된 텍스트가 Google·OpenAI 등 외부 AI 서비스로 전송됩니다.
            콘텐츠 <b className="text-[var(--ink)] font-semibold">생성 결과물</b>에서는 이메일·주민등록번호·전화번호 형식의 개인정보를
            정규식으로 찾아 자동으로 가립니다.
          </p>
          <p className="text-[var(--ink-3)] text-[13px]">
            다만 이 자동 마스킹은 콘텐츠 생성 경로에 적용되며, 형식이 일치하는 항목을 걸러내는 방식입니다.
            검사(OCR) 경로에는 아직 적용되어 있지 않고, 모든 형태의 개인정보를 완전히 제거한다고 보장하지 않습니다.
            개인정보 처리에 관한 자세한 내용은 <Link href="/privacy" className="text-[var(--brand-ink)] underline underline-offset-2 hover:text-[var(--ink)]">개인정보 처리방침</Link>을 참고해 주십시오.
          </p>
        </Section>

        <Section id="basis" title="6. 결과의 근거와 규제 기준일">
          <p>
            바름은 판정과 함께 근거가 되는 화장품법 조항·기준을 제시합니다. 적용 기준의 정식 명칭과 기준일은
            페이지 하단의 <b className="text-[var(--ink)] font-semibold">적용 기준</b> 표기에서 확인할 수 있으며,
            검사 리포트에는 그 검사 시점의 기준 스냅샷이 함께 기록됩니다.
          </p>
        </Section>

        <Section id="limits" title="7. 정확성·환각·최신성의 한계">
          <p>
            생성형 AI는 사실과 다른 내용을 그럴듯하게 만들어 낼 수 있습니다(환각).
            또한 같은 입력에도 실행마다 결과가 달라질 수 있고, 최신 법령·고시 변화가 즉시 반영되지 않을 수 있습니다.
            OCR 단계에서 문구를 잘못 읽으면 이후 판정도 영향을 받습니다.
            따라서 바름의 결과는 <b className="text-[var(--ink)] font-semibold">참고 정보</b>로 활용하고, 중요한 판단은 반드시 사람이 확인해야 합니다.
          </p>
        </Section>

        <Section id="human-review" title="8. 사람의 검토와 최종 책임">
          <p>
            바름은 사람의 판단을 돕는 사전 스크리너입니다. 광고를 실제로 게시할지에 대한
            <b className="text-[var(--ink)] font-semibold"> 최종 검토와 책임은 사업자(이용자)에게 있습니다.</b>
            &quot;통과&quot; 결과 역시 100% 안전을 보장하지 않으므로, 게시 전 사람의 확인을 권장합니다.
          </p>
        </Section>

        <Section id="report-error" title="9. 오류 신고와 재검토 절차">
          <p>
            판정이나 생성 결과에 오류가 있다고 판단되면 문구를 수정한 뒤 다시 검사할 수 있습니다.
            반복되거나 중요한 오류는 아래 문의 창구로 신고해 주시면 확인 후 반영하겠습니다.
            (데모 단계로, 정식 재검토·이의제기 절차는 정비 중입니다.)
          </p>
        </Section>

        <Section id="retention" title="10. 보관·수정·삭제">
          <p>
            입력·결과 자료의 저장 위치와 이용자 권리는 <Link href="/privacy" className="text-[var(--brand-ink)] underline underline-offset-2 hover:text-[var(--ink)]">개인정보 처리방침</Link>에서 안내합니다.
            현재 자동 파기와 이용자 직접 삭제 기능은 구현되어 있지 않으며 보관·파기 방침은 정비 중입니다.
            자료 삭제가 필요하면 문의 창구로 요청해 주십시오.
          </p>
        </Section>

        <Section id="security" title="11. 보안과 사고 대응">
          <p>
            업로드·생성 이미지는 비공개 저장소에 두고, 추측하기 어려운 접근 토큰을 통해서만 열람하도록 하고 있습니다.
            보안 사고 대응 절차와 통지 체계는 정식 서비스 시행 전 정비할 예정입니다.
          </p>
        </Section>

        <Section id="version" title="12. 정책 버전과 최종 업데이트">
          <p>
            본 안내는 <b className="text-[var(--ink)] font-semibold">{POLICY_VERSION}</b> 기준이며, 최종 업데이트 일자는 <b className="text-[var(--ink)] font-semibold">{LAST_UPDATED}</b>입니다.
            내용은 서비스 개선과 정책 변화에 따라 변경될 수 있으며, 변경 시 본 페이지에서 고지합니다.
          </p>
        </Section>
      </div>

      <PageFooter />
    </div>
  );
}
