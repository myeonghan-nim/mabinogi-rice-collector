package core

import "testing"

func TestComma(t *testing.T) {
	cases := map[int64]string{0: "0", 100: "100", 1000: "1,000", 45000: "45,000", 1234567: "1,234,567"}
	for n, want := range cases {
		if got := Comma(n); got != want {
			t.Errorf("Comma(%d) = %q, want %q", n, got, want)
		}
	}
}

func TestAlertText(t *testing.T) {
	// Python: 100*(1-100/1200) = 91.666... → "91.7"
	got := AlertText("마나 허브", 1200, 100)
	want := "🚨 마나 허브 특가! 일반 1,200 / 최저 100 / 할인율 91.7%"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestValidateItemName(t *testing.T) {
	if _, err := ValidateItemName("  ", nil); err == nil {
		t.Error("빈 이름 허용됨")
	}
	if _, err := ValidateItemName("숏,소드", nil); err == nil {
		t.Error("쉼표 허용됨")
	}
	if _, err := ValidateItemName("마나 허브", []string{"마나 허브"}); err == nil {
		t.Error("중복 허용됨")
	}
	got, err := ValidateItemName("  마나 허브  ", nil)
	if err != nil || got != "마나 허브" {
		t.Errorf("트림 실패: %q, %v", got, err)
	}
}
