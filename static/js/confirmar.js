// Pede confirmação antes de enviar um formulário marcado com
// data-confirmar="texto". Fica num arquivo próprio porque a política de
// segurança do site não aceita JavaScript escrito dentro do HTML.
document.addEventListener('submit', function (evento) {
  var mensagem = evento.target.getAttribute('data-confirmar');
  if (mensagem && !window.confirm(mensagem)) {
    evento.preventDefault();
  }
});
