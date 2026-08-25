"use client";

// 데모 전용: 원본 상세이미지 위에 교정 문구를 "제자리"에 얹은 고친 페이지 뷰.
// improve의 핵심을 보여준다 — 판매자 페이지를 새로 만드는 게 아니라 위반 표현만
// 그 자리에서 합법 문구로 바꾼 결과. 좌표·배경색·폰트는 픽스처(demo_corrections)에
// 미리 계산돼 있어(backend/scripts/bake_demo + 후처리) 클라이언트 연산이 없다.
// %좌표 + cqw 폰트라 어느 폭에서 렌더하든 이미지에 정확히 정렬된다.

export interface DemoCorrection {
  x_pct: number;
  y_pct: number;
  w_pct: number;
  h_pct: number;
  text: string;
  bg: string;
  fg: string;
  fs_cqw: number;
}

interface DemoFixedPageProps {
  imageUrl: string;
  corrections: DemoCorrection[];
}

export function DemoFixedPage({ imageUrl, corrections }: DemoFixedPageProps) {
  return (
    <div
      style={
        {
          position: "relative",
          width: "100%",
          maxWidth: 540,
          margin: "0 auto",
          containerType: "inline-size",
          overflow: "hidden",
          borderRadius: 6,
          boxShadow: "0 2px 24px rgba(0,0,0,.12)",
          background: "#fff",
        } as React.CSSProperties
      }
    >
      {/* 원본 판매자 이미지. 정적 자산이라 next/image 없이 그대로 얹는다(오버레이 정렬이 단순). */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imageUrl} alt="고친 상세페이지" style={{ width: "100%", display: "block" }} />
      {corrections.map((c, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: `${c.x_pct}%`,
            top: `${c.y_pct}%`,
            minWidth: `${c.w_pct}%`,
            minHeight: `${c.h_pct}%`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "1px 4px",
            boxSizing: "border-box",
            fontSize: `${c.fs_cqw}cqw`,
            fontWeight: 600,
            lineHeight: 1.16,
            textAlign: "center",
            wordBreak: "keep-all",
            borderRadius: 3,
            background: c.bg,
            color: c.fg,
          }}
        >
          {c.text}
        </div>
      ))}
    </div>
  );
}
