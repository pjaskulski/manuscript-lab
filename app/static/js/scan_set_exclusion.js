document.addEventListener("DOMContentLoaded", () => {
    const trainingSample = document.getElementById("is_training_sample");
    const testMaterial = document.getElementById("is_test_material");
    if (!trainingSample || !testMaterial) return;

    trainingSample.addEventListener("change", () => {
        if (trainingSample.checked) testMaterial.checked = false;
    });
    testMaterial.addEventListener("change", () => {
        if (testMaterial.checked) trainingSample.checked = false;
    });

    if (trainingSample.checked && testMaterial.checked) trainingSample.checked = false;
});
