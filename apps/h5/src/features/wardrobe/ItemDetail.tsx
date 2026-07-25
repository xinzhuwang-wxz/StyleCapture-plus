import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { Item, Ownership } from "../../api/client";
import { useSourceImage } from "./useSourceImage";

type ItemDetailProps = {
  item: Item | null;
  saving: boolean;
  onClose: () => void;
  onSave: (
    itemId: string,
    changes: {
      ownership: Ownership;
      corrections: Record<string, string>;
    }
  ) => void;
  onDeleteSource: (itemId: string) => void;
};

function DetailContent({
  item,
  saving,
  onClose,
  onSave,
  onDeleteSource
}: Omit<ItemDetailProps, "item"> & { item: Item }) {
  const imageUrl = useSourceImage(item.id, !item.source_available);
  const [ownership, setOwnership] = useState<Ownership>(item.ownership);
  const [category, setCategory] = useState(
    String(item.attributes.category?.value ?? "")
  );
  const [description, setDescription] = useState(
    String(item.attributes.description?.value ?? "")
  );
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    setOwnership(item.ownership);
    setCategory(String(item.attributes.category?.value ?? ""));
    setDescription(String(item.attributes.description?.value ?? ""));
    setConfirmingDelete(false);
  }, [item]);

  const isOwned = ownership === "owned";

  return (
    <motion.section
      className="pixel-sheet__content"
      style={{
        height: "100dvh",
        paddingTop: "max(var(--px-4), env(safe-area-inset-top))"
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="item-detail-title"
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", stiffness: 340, damping: 36 }}
    >
      {/* Top Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--px-4)",
          paddingBottom: "var(--px-3)",
          borderBottom: "2px dashed var(--pixel-border)"
        }}
      >
        <button
          type="button"
          className="pixel-button pixel-button--ghost"
          style={{ width: "2.5rem", height: "2.5rem", padding: 0 }}
          aria-label="返回衣橱"
          onClick={onClose}
        >
          ‹
        </button>
        <strong
          id="item-detail-title"
          className="pixel-subtitle"
          style={{ color: "var(--pixel-text)" }}
        >
          单品详情
        </strong>
        <span style={{ width: "2.5rem" }} />
      </div>

      {/* Image */}
      <div
        style={{
          height: "min(45dvh, 22rem)",
          marginBottom: "var(--px-4)",
          border: "3px solid var(--pixel-border)",
          boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
          overflow: "hidden",
          background: "var(--pixel-surface-raised)",
          display: "grid",
          placeItems: "center"
        }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={description || "衣橱单品"}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover"
            }}
          />
        ) : (
          <div
            style={{
              textAlign: "center",
              color: "var(--pixel-text-dim)"
            }}
          >
            <span style={{ fontSize: "4rem" }}>👕</span>
            <p
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.75rem",
                marginTop: "var(--px-2)"
              }}
            >
              原图不可用
            </p>
          </div>
        )}
      </div>

      {/* Meta */}
      <div
        style={{
          display: "flex",
          gap: "var(--px-2)",
          marginBottom: "var(--px-4)"
        }}
      >
        <span
          style={{
            padding: "var(--px-1) var(--px-3)",
            background: "var(--pixel-surface-raised)",
            border: "2px solid var(--pixel-border)",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.65rem",
            color: "var(--pixel-text-muted)"
          }}
        >
          {item.source_kind === "camera" ? "📷 拍照录入" : "🖼️ 相册录入"}
        </span>
        <span
          style={{
            padding: "var(--px-1) var(--px-3)",
            background: "var(--pixel-surface-raised)",
            border: "2px solid var(--pixel-border)",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.65rem",
            color:
              item.status === "ready"
                ? "var(--pixel-success)"
                : "var(--pixel-warning)"
          }}
        >
          {item.status === "ready" ? "✓ 已完成" : "🔄 处理中"}
        </span>
      </div>

      {/* Form Fields */}
      <div style={{ marginBottom: "var(--px-3)" }}>
        <label
          style={{
            display: "block",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.75rem",
            color: "var(--pixel-text-muted)",
            marginBottom: "var(--px-2)"
          }}
        >
          分类
        </label>
        <input
          value={category}
          maxLength={80}
          placeholder="例如：上装"
          onChange={(event) => setCategory(event.target.value)}
          style={{
            width: "100%",
            padding: "var(--px-3)",
            background: "var(--pixel-surface-raised)",
            border: "2px solid var(--pixel-border)",
            color: "var(--pixel-text)",
            fontFamily: "var(--font-body)",
            fontSize: "0.85rem",
            outline: "none"
          }}
        />
      </div>

      <div style={{ marginBottom: "var(--px-4)" }}>
        <label
          style={{
            display: "block",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.75rem",
            color: "var(--pixel-text-muted)",
            marginBottom: "var(--px-2)"
          }}
        >
          单品描述
        </label>
        <textarea
          value={description}
          maxLength={1000}
          rows={3}
          placeholder="补充更准确的描述"
          onChange={(event) => setDescription(event.target.value)}
          style={{
            width: "100%",
            padding: "var(--px-3)",
            background: "var(--pixel-surface-raised)",
            border: "2px solid var(--pixel-border)",
            color: "var(--pixel-text)",
            fontFamily: "var(--font-body)",
            fontSize: "0.85rem",
            resize: "vertical",
            outline: "none"
          }}
        />
      </div>

      {/* Ownership Toggle */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-2)",
          marginBottom: "var(--px-4)"
        }}
      >
        <button
          type="button"
          className="pixel-button"
          style={{
            background: isOwned ? "var(--pixel-accent)" : "var(--pixel-surface)",
            borderColor: isOwned ? "var(--pixel-accent-glow)" : "var(--pixel-border)",
            color: isOwned ? "var(--pixel-surface)" : "var(--pixel-text-muted)"
          }}
          onClick={() => setOwnership("owned")}
        >
          ⭐ 我的衣服
        </button>
        <button
          type="button"
          className="pixel-button"
          style={{
            background: !isOwned ? "var(--pixel-primary)" : "var(--pixel-surface)",
            borderColor: !isOwned ? "var(--pixel-primary-dark)" : "var(--pixel-border)",
            color: !isOwned ? "#fff" : "var(--pixel-text-muted)"
          }}
          onClick={() => setOwnership("inspiration")}
        >
          💖 穿搭灵感
        </button>
      </div>

      {/* Save Button */}
      <button
        type="button"
        className="pixel-button pixel-button--primary w-full"
        disabled={saving}
        onClick={() =>
          onSave(item.id, {
            ownership,
            corrections: {
              ...(category.trim() ? { category: category.trim() } : {}),
              ...(description.trim() ? { description: description.trim() } : {})
            }
          })
        }
        style={{ marginBottom: "var(--px-3)" }}
      >
        {saving ? "🔄 保存中…" : "💾 保存修改"}
      </button>

      {/* Delete Section */}
      {!item.source_available ? (
        <p
          style={{
            textAlign: "center",
            fontSize: "0.65rem",
            color: "var(--pixel-text-dim)",
            fontFamily: "var(--font-pixel)"
          }}
        >
          原图已删除，标签和描述仍可编辑
        </p>
      ) : confirmingDelete ? (
        <div
          style={{
            padding: "var(--px-4)",
            background: "rgba(248, 113, 113, 0.1)",
            border: "2px solid var(--pixel-error)",
            marginTop: "var(--px-3)"
          }}
        >
          <p
            style={{
              fontSize: "0.75rem",
              color: "var(--pixel-error)",
              fontFamily: "var(--font-pixel)",
              marginBottom: "var(--px-3)"
            }}
          >
            ⚠️ 删除后原图无法恢复
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "var(--px-2)"
            }}
          >
            <button
              type="button"
              className="pixel-button"
              onClick={() => setConfirmingDelete(false)}
            >
              保留原图
            </button>
            <button
              type="button"
              className="pixel-button"
              style={{
                background: "var(--pixel-error)",
                color: "#fff"
              }}
              onClick={() => onDeleteSource(item.id)}
            >
              确认删除
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirmingDelete(true)}
          style={{
            width: "100%",
            padding: "var(--px-3)",
            background: "transparent",
            border: "none",
            color: "var(--pixel-error)",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.7rem",
            cursor: "pointer"
          }}
        >
          🗑️ 删除原图
        </button>
      )}
    </motion.section>
  );
}

export function ItemDetail(props: ItemDetailProps) {
  return (
    <AnimatePresence>
      {props.item ? (
        <div
          className="pixel-sheet"
          style={{ alignItems: "flex-start", zIndex: 50 }}
          onClick={(e) => {
            if (e.target === e.currentTarget) props.onClose();
          }}
        >
          <DetailContent {...props} item={props.item} />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
