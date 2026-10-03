"use client";

import {
  IconBed,
  IconBowlSpoon,
  IconBuildingBank,
  IconBuildingStore,
  IconCake,
  IconCoffee,
  IconConfetti,
  IconFish,
  IconGlass,
  IconHome,
  IconInfoCircle,
  IconLeaf,
  IconMapPin,
  IconMeat,
  IconMountain,
  IconPizza,
  IconSoup,
  IconToolsKitchen3,
  IconTrees,
} from "@tabler/icons-react";

const iconMap = {
  "rice-bowl": IconBowlSpoon,
  "tools-kitchen-3": IconToolsKitchen3,
  burger: IconMeat,
  leaf: IconLeaf,
  fish: IconFish,
  coffee: IconCoffee,
  japanese: IconBowlSpoon,
  korean: IconSoup,
  italian: IconPizza,
  "hot-pot": IconSoup,
  breakfast: IconToolsKitchen3,
  desserts: IconCake,
  drinks: IconGlass,
  taiwanese: IconBowlSpoon,
  "beef-noodles": IconSoup,
  confetti: IconConfetti,
  "building-store": IconBuildingStore,
  bed: IconBed,
  home: IconHome,
  "info-circle": IconInfoCircle,
  trees: IconTrees,
  "building-bank": IconBuildingBank,
  mountain: IconMountain,
  "map-pin": IconMapPin,
};

export type IconOption = {
  value: string;
  label: string;
  iconKey?: string;
  color?: string;
};

export const cuisineIconOptions = [
  { value: "rice-bowl", label: "飯碗" },
  { value: "tools-kitchen-3", label: "餐飲" },
  { value: "burger", label: "漢堡" },
  { value: "leaf", label: "蔬食" },
  { value: "fish", label: "海鮮" },
  { value: "coffee", label: "咖啡" },
  { value: "japanese", label: "日本料理" },
  { value: "korean", label: "韓式料理" },
  { value: "italian", label: "義式料理" },
  { value: "hot-pot", label: "火鍋" },
  { value: "breakfast", label: "早餐" },
  { value: "desserts", label: "甜點" },
  { value: "drinks", label: "飲料" },
  { value: "taiwanese", label: "台灣料理" },
  { value: "beef-noodles", label: "牛肉麵" },
] as const;

export const tourismIconOptions = [
  { value: "tourism-food", label: "餐飲", iconKey: "tools-kitchen-3", color: "#F26B4F" },
  { value: "tourism-attraction", label: "景點", iconKey: "map-pin", color: "#657B8C" },
  { value: "tourism-lodging", label: "旅館民宿", iconKey: "bed", color: "#8B6BB1" },
  {
    value: "tourism-service-site",
    label: "旅遊服務站",
    iconKey: "info-circle",
    color: "#4E8F6B",
  },
] as const;

export function CuisineIcon({ iconKey, size = 22 }: { iconKey: string; size?: number }) {
  const IconComponent = iconMap[iconKey as keyof typeof iconMap] ?? IconToolsKitchen3;
  return <IconComponent size={size} stroke={1.8} aria-hidden="true" />;
}

export function TourismIcon({ iconKey, size = 22 }: { iconKey: string; size?: number }) {
  return <CuisineIcon iconKey={iconKey} size={size} />;
}

export function CuisineIconPicker({
  value,
  onChange,
  options = cuisineIconOptions,
  ariaLabel = "選擇圖示分類",
  color = "#F26B4F",
}: {
  value: string;
  onChange: (value: string) => void;
  options?: readonly IconOption[];
  ariaLabel?: string;
  color?: string;
}) {
  return (
    <div className="cuisine-icon-picker" role="radiogroup" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? "is-selected" : undefined}
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          title={option.label}
        >
          <span
            className="icon-color-marker"
            style={{ backgroundColor: option.color ?? color }}
          >
            <CuisineIcon iconKey={option.iconKey ?? option.value} size={20} />
          </span>
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
}

export function TourismIconPicker({
  value,
  onChange,
  options = tourismIconOptions,
  color = "#F26B4F",
}: {
  value: string;
  onChange: (value: string) => void;
  options?: readonly IconOption[];
  color?: string;
}) {
  return (
    <div className="place-icon-picker" role="radiogroup" aria-label="選擇觀光資料圖示">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? "is-selected" : undefined}
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          title={option.label}
        >
          <span
            className="icon-color-marker"
            style={{ backgroundColor: option.color ?? color }}
          >
            <TourismIcon iconKey={option.iconKey ?? option.value} size={20} />
          </span>
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
}
