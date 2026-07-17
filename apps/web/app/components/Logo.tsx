/* Shapiqo-logotypen enligt varumärkesguiden: badge med lutande lime-S på
   navy-gradient + wordmark i Montserrat ExtraBold. Byggd i CSS så den är
   skarp i alla storlekar. På mörk bakgrund inverteras badgen (lime platta,
   navy S) och wordmarken blir vit. */

const FONT = "var(--font-montserrat), Montserrat, Arial, sans-serif";

export default function Logo({
  badge = 32,
  name = 17,
  className = "",
}: {
  badge?: number;
  name?: number; // 0 = bara badgen (t.ex. mycket små ytor)
  className?: string;
}) {
  return (
    <a
      href="/"
      aria-label="Shapiqo — startsida"
      className={`flex items-center gap-2.5 ${className}`}
    >
      <span
        className="flex shrink-0 items-center justify-center bg-[linear-gradient(135deg,#23588a,#19325b)] text-[#a1e645] dark:bg-none dark:bg-[#a1e645] dark:text-[#13284b]"
        style={{
          width: badge,
          height: badge,
          borderRadius: badge * 0.27,
          fontFamily: FONT,
          fontWeight: 800,
          fontStyle: "italic",
          fontSize: badge * 0.6,
          textIndent: -1,
        }}
      >
        S
      </span>
      {name > 0 && (
        <span
          className="text-[#19325b] dark:text-white"
          style={{
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: name,
            letterSpacing: "-0.5px",
          }}
        >
          SHAPIQO
        </span>
      )}
    </a>
  );
}
