import type { Metadata } from "next";
import Link from "next/link";
import { PageFooter } from "@/components/PageFooter/PageFooter";

// 정책 버전·최종 업데이트. 문서 개정 시 이 두 값만 갱신한다.
const POLICY_VERSION = "v0.1 (데모)";
const LAST_UPDATED = "2026-08-24";

export const metadata: Metadata = {
  title: "개인정보 처리방침 | 바름",
  description:
    "바름 데모 서비스의 개인정보 처리방침 안내. 수집 항목, 처리·저장 위치, 제3자 처리위탁과 국외 전송, 보관·파기 방침을 안내합니다.",
};

/** 문서 섹션 한 덩어리. 제목(h2)과 본문을 감싼다. */
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

export default function PrivacyPolicyPage() {
  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 w-full max-w-[820px] mx-auto px-[24px] py-[44px] max-[640px]:px-[18px] max-[640px]:py-[30px]">
        {/* 데모 단계 고지 배너: 상태색(빨강·앰버)이 아니라 중립 표면+테두리로. 경보가 아니라 안내다 */}
        <div className="flex items-start gap-[10px] border border-[var(--line-2)] bg-[var(--surface-sub)] p-[13px_16px] text-[13px] leading-[1.7] text-[var(--ink-2)] break-keep">
          <span aria-hidden="true" className="font-mono text-[var(--ink-3)] font-bold shrink-0 pt-[1px]">ⓘ</span>
          <span>
            본 문서는 <b className="text-[var(--ink)] font-semibold">데모 단계의 안내</b>이며, 실제 서비스 시행 전
            법률·개인정보 전문가의 검토가 필요합니다. 아래 내용은 현재 구현을 기준으로 작성했고,
            아직 확정되지 않은 항목은 &quot;정비 중&quot;으로 표기했습니다.
          </span>
        </div>

        {/* 제목 + 버전/일자 */}
        <div className="mt-[30px]">
          <div className="text-[var(--brand-ink)] mb-[10px] font-mono text-[11.5px] font-bold tracking-[0.4px]">
            개인정보 처리방침
          </div>
          <h1 className="m-0 text-[var(--ink)] text-[32px] font-extrabold leading-[1.25] tracking-[-1px] break-keep">
            바름 개인정보 처리방침
          </h1>
          <div className="mt-[12px] flex flex-wrap items-center gap-x-[14px] gap-y-[4px] text-[var(--ink-3)] font-mono text-[11.5px]">
            <span>버전 {POLICY_VERSION}</span>
            <span aria-hidden="true">·</span>
            <span>최종 업데이트 {LAST_UPDATED}</span>
          </div>
        </div>

        <Section id="overview" title="1. 개요">
          <p>
            바름은 화장품 광고 문구와 상세페이지의 화장품법 위반 위험을 게시 전에 사전 점검하는 도구입니다.
            이 처리방침은 바름이 서비스 제공 과정에서 어떤 정보를 수집하고, 어디에 저장하며,
            어떤 외부 처리자에게 위탁하는지를 안내합니다. 바름은 현재 데모 단계이며, 세부 정책은 계속 정비하고 있습니다.
          </p>
        </Section>

        <Section id="items" title="2. 수집하는 정보와 목적">
          <p>바름은 검사와 콘텐츠 초안 제작에 필요한 최소한의 자료만 다룹니다.</p>
          <ul className="list-disc pl-[20px] space-y-[8px] marker:text-[var(--ink-3)]">
            <li>
              <b className="text-[var(--ink)] font-semibold">업로드한 상세페이지 이미지·제품사진</b> - 광고 위반 점검과
              상세페이지 초안·배경 이미지 생성에 사용합니다.
            </li>
            <li>
              <b className="text-[var(--ink)] font-semibold">이미지에서 추출한 광고 텍스트(OCR 결과)</b> - 위반 문구 판정과
              대체 문구 제안에 사용합니다.
            </li>
            <li>
              <b className="text-[var(--ink)] font-semibold">결제·수출 프로필 등 이용자가 입력한 설정값</b> - 이 값들은
              브라우저의 localStorage에만 저장되며 바름 서버로 전송되지 않습니다.
            </li>
          </ul>
          <p className="text-[var(--ink-3)] text-[13px]">
            바름은 위 목적 범위를 벗어나 이용자를 식별·추적하기 위한 별도의 개인정보를 요구하지 않습니다.
            업로드한 자료 안에 개인정보(예: 이메일, 전화번호)가 포함될 수 있으므로,
            필요하지 않은 개인정보는 업로드 전에 이용자가 직접 가려주시길 권장합니다.
          </p>
        </Section>

        <Section id="storage" title="3. 처리·저장 위치">
          <p>
            검사·생성 대상 이미지와 결과는 접근이 제한된 저장소에 보관합니다.
          </p>
          <ul className="list-disc pl-[20px] space-y-[8px] marker:text-[var(--ink-3)]">
            <li>
              업로드 이미지·생성 이미지는 <b className="text-[var(--ink)] font-semibold">Supabase의 비공개(private) 스토리지 버킷</b>에
              저장하며, 추측하기 어려운 접근 토큰을 아는 경우에만 해당 파일을 열람할 수 있습니다.
            </li>
            <li>
              검사 이력과 판정 결과는 <b className="text-[var(--ink)] font-semibold">checks 테이블(데이터베이스)</b>에 저장합니다.
            </li>
          </ul>
        </Section>

        <Section id="processors" title="4. 제3자 처리위탁 및 국외 이전">
          <p>
            바름은 AI 처리와 저장을 위해 아래 외부 서비스에 일부 업무를 위탁합니다.
            이 과정에서 이용자가 업로드한 이미지와 추출된 텍스트가 국외에 있는 서버로 전송·처리될 수 있습니다.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px] leading-[1.6]">
              <thead>
                <tr className="border-b border-[var(--line-2)] text-left text-[var(--ink-3)] font-mono text-[11.5px]">
                  <th className="py-[8px] pr-[12px] font-semibold">수탁자</th>
                  <th className="py-[8px] pr-[12px] font-semibold">위탁 업무</th>
                  <th className="py-[8px] font-semibold">전달되는 항목</th>
                </tr>
              </thead>
              <tbody className="text-[var(--ink-2)]">
                <tr className="border-b border-[var(--line)]">
                  <td className="py-[10px] pr-[12px] align-top font-semibold text-[var(--ink)]">Google (Gemini)</td>
                  <td className="py-[10px] pr-[12px] align-top">이미지 텍스트 추출(OCR), 대체·상세페이지 문구 생성, 배경 이미지 생성</td>
                  <td className="py-[10px] align-top">업로드 이미지, 추출·입력 텍스트</td>
                </tr>
                <tr className="border-b border-[var(--line)]">
                  <td className="py-[10px] pr-[12px] align-top font-semibold text-[var(--ink)]">OpenAI</td>
                  <td className="py-[10px] pr-[12px] align-top">광고 위반 여부 판정</td>
                  <td className="py-[10px] align-top">추출·입력 텍스트</td>
                </tr>
                <tr className="border-b border-[var(--line)]">
                  <td className="py-[10px] pr-[12px] align-top font-semibold text-[var(--ink)]">Supabase</td>
                  <td className="py-[10px] pr-[12px] align-top">이미지·검사 이력 저장(비공개 버킷·데이터베이스)</td>
                  <td className="py-[10px] align-top">업로드·생성 이미지, 검사 결과</td>
                </tr>
                <tr>
                  <td className="py-[10px] pr-[12px] align-top font-semibold text-[var(--ink)]">LangSmith</td>
                  <td className="py-[10px] pr-[12px] align-top">관측·디버깅용 트레이싱(설정이 켜진 경우에 한함)</td>
                  <td className="py-[10px] align-top">AI 호출의 일부 입력·출력</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-[var(--ink-3)] text-[13px]">
            각 수탁자의 실제 데이터 처리 조건은 해당 사업자의 정책을 따르며,
            바름과 각 사업자 사이의 세부 계약·설정은 정식 서비스 시행 전 확정·검토할 예정입니다.
          </p>
        </Section>

        <Section id="transfer" title="5. 개인정보의 국외 전송">
          <p>
            위 4항에 따라 이용자가 업로드한 이미지와 추출된 텍스트는 Google·OpenAI 등
            국외에 서버를 둔 사업자에게 전송되어 처리됩니다. 이는 AI 기반 검사·생성 기능을 제공하기 위한 것입니다.
            개인정보가 포함될 수 있는 자료를 국외 처리에 맡기고 싶지 않다면, 해당 자료의 업로드를 피해 주십시오.
          </p>
        </Section>

        <Section id="retention" title="6. 보관 및 파기">
          <p>
            현재 바름에는 업로드·검사 자료의 자동 파기 기능과 이용자가 직접 자료를 삭제하는 기능이
            아직 구현되어 있지 않습니다. 보관 기간과 파기 절차는 <b className="text-[var(--ink)] font-semibold">정비 중</b>이며,
            구체적인 보관 기간은 아직 확정된 약속으로 제시하지 않습니다.
            자료 삭제가 필요한 경우 아래 문의 창구로 요청해 주시면 개별적으로 처리하겠습니다.
          </p>
        </Section>

        <Section id="training" title="7. AI 학습 이용 여부">
          <p>
            바름은 이용자가 올린 자료를 서비스 제공(검사·생성) 목적으로만 사용하며,
            현재 이를 자체 AI 모델의 학습·개선 용도로 이용하지 않습니다.
            다만 Google·OpenAI 등 외부 AI 사업자의 데이터 취급 조건은 각 사업자의 정책과 계약에 따르며,
            이 부분은 정식 서비스 전 확인·정비할 예정입니다. 따라서 본 항목은 현재 방침에 대한 안내이며,
            모든 외부 처리에 대한 법적 보증으로 단정하지 않습니다.
          </p>
        </Section>

        <Section id="rights" title="8. 이용자의 권리와 요청 방법">
          <p>
            이용자는 자신이 업로드한 자료의 처리 현황 확인, 자료 삭제, 처리 정지 등을 요청할 수 있습니다.
            브라우저에만 저장되는 결제·수출 프로필 등은 브라우저의 저장소를 비우면 즉시 삭제됩니다.
            그 밖의 요청은 아래 문의 창구를 통해 접수해 주시면 확인 후 처리하겠습니다.
          </p>
        </Section>

        <Section id="contact" title="9. 문의">
          <p>
            개인정보 처리와 관련한 문의·요청은 아래 창구로 접수해 주십시오.
            (데모 단계로, 정식 개인정보 보호책임자 지정과 창구 정비는 진행 중입니다.)
          </p>
          <ul className="list-disc pl-[20px] space-y-[6px] marker:text-[var(--ink-3)]">
            <li>서비스 소개 및 문의: <Link href="/" className="text-[var(--brand-ink)] underline underline-offset-2 hover:text-[var(--ink)]">바름 홈</Link></li>
            <li>AI 처리에 관한 안내: <Link href="/policy/ai" className="text-[var(--brand-ink)] underline underline-offset-2 hover:text-[var(--ink)]">AI 이용 안내</Link></li>
          </ul>
        </Section>

        <Section id="revision" title="10. 고지 및 개정">
          <p>
            본 처리방침의 내용은 서비스 개선과 법령·정책 변화에 따라 변경될 수 있으며,
            변경 시 본 페이지의 버전과 최종 업데이트 일자를 통해 고지합니다.
          </p>
        </Section>
      </div>

      <PageFooter />
    </div>
  );
}
